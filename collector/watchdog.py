#!/usr/bin/env python3
"""Self-healing health check for the collector, relay, and GitHub mirror."""

from __future__ import annotations

import base64
import contextlib
import grp
import json
import os
import subprocess
import tempfile
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DATA_DIR = Path(os.environ.get("FOOTBALL_AI_DATA_DIR", "/var/lib/football-ai"))
MIRROR_URL = os.environ.get(
    "FOOTBALL_AI_MIRROR_URL",
    "https://raw.githubusercontent.com/xtilq96-ctrl/football-analysis-lab/live-data/latest.json",
)
MIRROR_FALLBACK_URL = os.environ.get(
    "FOOTBALL_AI_MIRROR_FALLBACK_URL",
    "https://api.github.com/repos/xtilq96-ctrl/football-analysis-lab/contents/latest.json?ref=live-data",
)
MIRROR_CDN_URL = "https://cdn.jsdelivr.net/gh/xtilq96-ctrl/football-analysis-lab@live-data/latest.json"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def age_minutes(value: str) -> float:
    return max(0.0, (utc_now() - datetime.fromisoformat(value)).total_seconds() / 60)


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    handle, temporary = tempfile.mkstemp(prefix=f".{path.name}", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, separators=(",", ":"))
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        os.chown(path, 0, grp.getgrnam("football-ai").gr_gid)
        os.chmod(path, 0o640)
    finally:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(temporary)


def service_active(name: str) -> bool:
    result = subprocess.run(
        ["systemctl", "is-active", "--quiet", name], check=False,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    return result.returncode == 0


def read_latest() -> dict[str, Any]:
    return json.loads((DATA_DIR / "latest.json").read_text(encoding="utf-8"))


def deadline_errors(payload: dict[str, Any]) -> list[str]:
    now = utc_now()
    missed_analysis = missing_had = missed_locks = 0
    for match in payload.get("matches") or []:
        if match.get("businessDate") != payload.get("businessDate"):
            continue
        schedule = match.get("analysisSchedule") or {}
        try:
            final_at = datetime.fromisoformat(str(schedule["finalAnalysisAt"]))
            lock_at = datetime.fromisoformat(str(schedule["lockAt"]))
        except (KeyError, TypeError, ValueError):
            continue
        if now >= final_at.astimezone(timezone.utc) and not (match.get("analysis") or {}).get("probabilities"):
            if not match.get("had"):
                missing_had += 1
            else:
                missed_analysis += 1
        if now >= lock_at.astimezone(timezone.utc) and not schedule.get("isLocked"):
            missed_locks += 1
    errors = []
    if missing_had:
        errors.append(f"{missing_had}场比赛因体彩未提供胜平负赔率，最终分析保持待评估")
    if missed_analysis:
        errors.append(f"{missed_analysis}场比赛超过最终分析时间仍未生成结果")
    if missed_locks:
        errors.append(f"{missed_locks}场比赛超过锁定时间仍未锁定")
    return errors


def mirror_payload() -> dict[str, Any]:
    failures = []
    for url in dict.fromkeys((MIRROR_URL, MIRROR_FALLBACK_URL, MIRROR_CDN_URL)):
        separator = "&" if "?" in url else "?"
        request = urllib.request.Request(
            f"{url}{separator}health={int(utc_now().timestamp())}",
            headers={
                "Accept": "application/vnd.github.raw+json",
                "User-Agent": "FootballAIWatchdog/1.0",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                envelope = json.loads(response.read())
            if envelope.get("bodyBase64"):
                return json.loads(base64.b64decode(envelope["bodyBase64"]))
            return json.loads(envelope["body"])
        except Exception as error:  # try the next GitHub-backed endpoint
            failures.append(f"{url}: {error}")
    raise RuntimeError("；".join(failures))


def main() -> int:
    previous = None
    with contextlib.suppress(OSError, ValueError):
        previous = json.loads((DATA_DIR / "watchdog.json").read_text(encoding="utf-8"))
    services = {
        "collectorTimer": service_active("football-ai-collector.timer"),
        "relay": service_active("football-ai-relay.service"),
        "nginx": service_active("nginx.service"),
    }
    errors: list[str] = []
    local_age = None
    local_payload = None
    try:
        local_payload = read_latest()
        local_age = round(age_minutes(str(local_payload["updatedAt"])), 1)
    except (OSError, ValueError, KeyError, TypeError) as error:
        errors.append(f"本地数据读取失败：{error}")
    if local_age is None or local_age > 15:
        subprocess.run(["systemctl", "start", "football-ai-collector.service"], check=False)
        try:
            local_payload = read_latest()
            local_age = round(age_minutes(str(local_payload["updatedAt"])), 1)
        except (OSError, ValueError, KeyError, TypeError):
            pass
    if local_age is None or local_age > 15:
        errors.append("采集数据超过15分钟未更新")
    if local_payload:
        errors.extend(deadline_errors(local_payload))
    for name, active in services.items():
        if not active:
            errors.append(f"服务未运行：{name}")
    mirror_age = None
    mirror_failure_count = 0
    try:
        mirror_age = round(age_minutes(str(mirror_payload()["updatedAt"])), 1)
        if mirror_age > 20:
            errors.append("GitHub网站快照超过20分钟未更新")
    except Exception as error:  # network failures are intentionally converted to health state
        mirror_failure_count = int((previous or {}).get("mirrorFailureCount") or 0) + 1
        if mirror_failure_count >= 3:
            errors.append(f"GitHub网站快照连续检查失败：{error}")
    status = "ok" if not errors else "warning"
    payload = {
        "status": status, "checkedAt": utc_now().isoformat(timespec="seconds"),
        "localDataAgeMinutes": local_age, "mirrorAgeMinutes": mirror_age,
        "mirrorFailureCount": mirror_failure_count,
        "services": services, "autoRetry": True, "errors": errors,
    }
    atomic_json(DATA_DIR / "watchdog.json", payload)
    if not previous or previous.get("status") != status or previous.get("errors") != errors:
        with (DATA_DIR / "alerts.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

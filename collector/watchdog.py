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


def mirror_payload() -> dict[str, Any]:
    request = urllib.request.Request(
        f"{MIRROR_URL}?health={int(utc_now().timestamp())}",
        headers={"Accept": "application/json", "User-Agent": "FootballAIWatchdog/1.0"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        envelope = json.loads(response.read())
    if envelope.get("bodyBase64"):
        return json.loads(base64.b64decode(envelope["bodyBase64"]))
    return json.loads(envelope["body"])


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
    try:
        local_age = round(age_minutes(str(read_latest()["updatedAt"])), 1)
    except (OSError, ValueError, KeyError, TypeError) as error:
        errors.append(f"本地数据读取失败：{error}")
    if local_age is None or local_age > 15:
        subprocess.run(["systemctl", "start", "football-ai-collector.service"], check=False)
        try:
            local_age = round(age_minutes(str(read_latest()["updatedAt"])), 1)
        except (OSError, ValueError, KeyError, TypeError):
            pass
    if local_age is None or local_age > 15:
        errors.append("采集数据超过15分钟未更新")
    for name, active in services.items():
        if not active:
            errors.append(f"服务未运行：{name}")
    mirror_age = None
    try:
        mirror_age = round(age_minutes(str(mirror_payload()["updatedAt"])), 1)
        if mirror_age > 20:
            errors.append("GitHub网站快照超过20分钟未更新")
    except Exception as error:  # network failures are intentionally converted to health state
        errors.append(f"GitHub网站快照检查失败：{error}")
    status = "ok" if not errors else "warning"
    payload = {
        "status": status, "checkedAt": utc_now().isoformat(timespec="seconds"),
        "localDataAgeMinutes": local_age, "mirrorAgeMinutes": mirror_age,
        "services": services, "autoRetry": True, "errors": errors,
    }
    atomic_json(DATA_DIR / "watchdog.json", payload)
    if not previous or previous.get("status") != status or previous.get("errors") != errors:
        with (DATA_DIR / "alerts.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())

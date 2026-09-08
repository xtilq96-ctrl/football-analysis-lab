#!/usr/bin/env python3
"""China Sporttery football collector.

Fetches the official HAD/HHAD feed, keeps current matches and immutable odds
history in SQLite, and publishes small JSON files for the web/API layer.
Only Python's standard library is required on Ubuntu 22.04.
"""

from __future__ import annotations

import argparse
import contextlib
import functools
import gzip
import hashlib
import json
import logging
import math
import os
import sqlite3
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

try:
    import fcntl  # Linux production lock; unavailable on Windows test hosts.
except ImportError:  # pragma: no cover - exercised only during Windows validation
    fcntl = None  # type: ignore[assignment]


SPORTTERY_URL = (
    "https://webapi.sporttery.cn/gateway/uniform/football/"
    "getMatchCalculatorV1.qry?channel=c&poolCode=had,hhad"
)
SHANGHAI = timezone(timedelta(hours=8))
HEADERS = {
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Origin": "https://m.sporttery.cn",
    "Referer": "https://m.sporttery.cn/mjc/jsq/zqspf/",
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) "
        "AppleWebKit/605.1.15 Version/17.5 Mobile/15E148 Safari/604.1"
    ),
    "X-Requested-With": "XMLHttpRequest",
}


def now_shanghai() -> datetime:
    return datetime.now(SHANGHAI)


def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, separators=(",", ":"))
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, path)
    finally:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(temp_name)


def fetch_payload(url: str, timeout: float, retries: int = 3) -> tuple[dict[str, Any], bytes]:
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            request = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read()
                if response.status != 200:
                    raise RuntimeError(f"official endpoint returned HTTP {response.status}")
            payload = json.loads(raw)
            if payload.get("success") is not True or str(payload.get("errorCode")) != "0":
                raise RuntimeError("official endpoint returned an unsuccessful payload")
            if not isinstance(payload.get("value", {}).get("matchInfoList"), list):
                raise RuntimeError("official endpoint payload has an unexpected structure")
            return payload, raw
        except (OSError, ValueError, urllib.error.URLError, RuntimeError) as error:
            last_error = error
            if attempt < retries:
                time.sleep(2 ** (attempt - 1))
    raise RuntimeError(f"fetch failed after {retries} attempts: {last_error}")


def flatten_matches(payload: dict[str, Any]) -> list[dict[str, Any]]:
    # The endpoint can return the same match in more than one pool group. Merge
    # those records so one fixture is counted and saved exactly once.
    matches: dict[str, dict[str, Any]] = {}
    for group in payload.get("value", {}).get("matchInfoList", []):
        business_date = str(group.get("businessDate") or "")
        for match in group.get("subMatchList") or []:
            if not isinstance(match, dict):
                continue
            item = dict(match)
            item["businessDate"] = str(item.get("businessDate") or business_date)
            if item.get("matchId") is None:
                continue
            key = str(item["matchId"])
            matches[key] = {**matches.get(key, {}), **item}
    return sorted(matches.values(), key=lambda item: int(item.get("matchNum") or 0))


def decimal_odds(value: Any) -> float | None:
    try:
        parsed = float(value)
        return parsed if parsed > 1 else None
    except (TypeError, ValueError):
        return None


def poisson_probabilities(rate: float, maximum: int = 10) -> list[float]:
    values = [math.exp(-rate)]
    for goals in range(1, maximum + 1):
        values.append(values[-1] * rate / goals)
    return values


def outcome_probabilities(home_rate: float, away_rate: float) -> tuple[float, float, float]:
    home_goals = poisson_probabilities(home_rate)
    away_goals = poisson_probabilities(away_rate)
    home = draw = away = 0.0
    for home_score, home_probability in enumerate(home_goals):
        for away_score, away_probability in enumerate(away_goals):
            probability = home_probability * away_probability
            if home_score > away_score:
                home += probability
            elif home_score == away_score:
                draw += probability
            else:
                away += probability
    total = home + draw + away
    return home / total, draw / total, away / total


@functools.lru_cache(maxsize=2048)
def fit_expected_goals(target: tuple[float, float, float]) -> tuple[float, float]:
    best = (1.35, 1.15)
    best_error = float("inf")
    for home_step in range(5, 81):
        home_rate = home_step * 0.05
        for away_step in range(5, 71):
            away_rate = away_step * 0.05
            model = outcome_probabilities(home_rate, away_rate)
            total_penalty = max(0.0, home_rate + away_rate - 4.5) ** 2 * 0.01
            error = sum((model[index] - target[index]) ** 2 for index in range(3)) + total_penalty
            if error < best_error:
                best_error = error
                best = (home_rate, away_rate)
    return best


def score_model(probabilities: list[float]) -> dict[str, Any]:
    home_rate, away_rate = fit_expected_goals(tuple(value / 100 for value in probabilities))
    home_goals = poisson_probabilities(home_rate)
    away_goals = poisson_probabilities(away_rate)
    scores: list[tuple[int, int, float]] = []
    for home_score, home_probability in enumerate(home_goals):
        for away_score, away_probability in enumerate(away_goals):
            scores.append((home_score, away_score, home_probability * away_probability * 100))
    scores.sort(key=lambda item: item[2], reverse=True)
    predicted_outcome = probabilities.index(max(probabilities))
    predicted = next(
        item for item in scores
        if (predicted_outcome == 0 and item[0] > item[1])
        or (predicted_outcome == 1 and item[0] == item[1])
        or (predicted_outcome == 2 and item[0] < item[1])
    )

    total_rate = home_rate + away_rate
    total_distribution = poisson_probabilities(total_rate, 6)
    covered = sum(total_distribution)
    totals = {str(index): round(value * 100, 2) for index, value in enumerate(total_distribution)}
    totals["7+"] = round(max(0.0, 1 - covered) * 100, 2)
    predicted_total = max(totals, key=totals.get)
    under_25 = sum(total_distribution[:3]) * 100
    return {
        "modelVersion": "v1-market-poisson",
        "expectedGoals": {"home": round(home_rate, 2), "away": round(away_rate, 2), "total": round(total_rate, 2)},
        "predictedScore": f"{predicted[0]}-{predicted[1]}",
        "scoreProbabilities": [
            {"score": f"{home_score}-{away_score}", "probability": round(probability, 2)}
            for home_score, away_score, probability in scores[:5]
        ],
        "predictedTotalGoals": predicted_total,
        "totalGoalsProbabilities": totals,
        "under25Probability": round(under_25, 2),
        "over25Probability": round(100 - under_25, 2),
    }


def market_analysis(match: dict[str, Any]) -> dict[str, Any]:
    had = match.get("had") or {}
    odds = [decimal_odds(had.get(key)) for key in ("h", "d", "a")]
    if any(value is None for value in odds):
        return {"probabilities": None, "prediction": None, "confidence": None, "risk": "待评估", "marketMargin": None}
    implied = [1 / value for value in odds if value is not None]
    total = sum(implied)
    probabilities = [round(value / total * 100, 2) for value in implied]
    labels = ["主胜", "平局", "客胜"]
    ordered = sorted(probabilities, reverse=True)
    gap = ordered[0] - ordered[1]
    risk = "低风险" if gap >= 25 else "中风险" if gap >= 12 else "高风险"
    return {
        "probabilities": dict(zip(("home", "draw", "away"), probabilities)),
        "prediction": labels[probabilities.index(max(probabilities))],
        "confidence": round(max(probabilities), 2),
        "risk": risk,
        "marketMargin": round((total - 1) * 100, 2),
        **score_model(probabilities),
    }


def build_recommendations(matches: list[dict[str, Any]], business_dates: list[str]) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    pick_key = {"主胜": "h", "平局": "d", "客胜": "a"}
    for business_date in business_dates:
        candidates: list[dict[str, Any]] = []
        for item in matches:
            if item.get("businessDate") != business_date:
                continue
            analysis = item.get("analysis") or {}
            prediction = analysis.get("prediction")
            confidence = float(analysis.get("confidence") or 0)
            price = decimal_odds((item.get("had") or {}).get(pick_key.get(prediction)))
            if prediction not in pick_key or confidence < 42 or price is None:
                continue
            candidates.append({
                "matchId": item["matchId"],
                "officialNumber": item["officialNumber"],
                "league": item["league"],
                "home": item["home"],
                "away": item["away"],
                "pick": prediction,
                "probability": confidence,
                "odds": price,
                "quality": confidence - float(analysis.get("marketMargin") or 0) * 0.35,
            })
        pairs: list[dict[str, Any]] = []
        for left_index, left in enumerate(candidates):
            for right in candidates[left_index + 1:]:
                combined_probability = left["probability"] * right["probability"] / 100
                diversity_bonus = 2 if left["league"] != right["league"] else 0
                score = combined_probability + diversity_bonus + (left["quality"] + right["quality"]) * 0.05
                pairs.append({
                    "legs": [{key: value for key, value in leg.items() if key not in {"quality"}} for leg in (left, right)],
                    "combinedProbability": round(combined_probability, 2),
                    "combinedOdds": round(left["odds"] * right["odds"], 2),
                    "level": "稳健" if combined_probability >= 30 else "均衡" if combined_probability >= 23 else "观察",
                    "_score": score,
                })
        pairs.sort(key=lambda item: item["_score"], reverse=True)
        selected: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for pair in pairs:
            identity = tuple(sorted(leg["matchId"] for leg in pair["legs"]))
            if identity in seen:
                continue
            seen.add(identity)
            pair.pop("_score", None)
            selected.append(pair)
            if len(selected) == 3:
                break
        result[business_date] = selected
    return result


def official_number(match: dict[str, Any]) -> str:
    if match.get("matchNumStr"):
        return str(match["matchNumStr"])
    number = int(match.get("matchNum") or 0) % 1000
    return f"{match.get('matchWeek', '')}{number:03d}"


def normalized(match: dict[str, Any], collected_at: str) -> dict[str, Any]:
    return {
        "matchId": str(match["matchId"]),
        "businessDate": str(match.get("businessDate") or ""),
        "officialNumber": official_number(match),
        "matchNumber": int(match.get("matchNum") or 0),
        "league": str(match.get("leagueAllName") or ""),
        "home": str(match.get("homeTeamAllName") or ""),
        "away": str(match.get("awayTeamAllName") or ""),
        "kickoffDate": str(match.get("matchDate") or ""),
        "kickoffTime": str(match.get("matchTime") or ""),
        "saleStatus": str(match.get("sellStatus") or ""),
        "had": match.get("had"),
        "hhad": match.get("hhad"),
        "analysis": market_analysis(match),
        "collectedAt": collected_at,
    }


SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
CREATE TABLE IF NOT EXISTS collector_runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  status TEXT NOT NULL,
  match_count INTEGER NOT NULL DEFAULT 0,
  error TEXT
);
CREATE TABLE IF NOT EXISTS current_matches (
  match_id TEXT PRIMARY KEY,
  business_date TEXT NOT NULL,
  official_number TEXT NOT NULL,
  match_number INTEGER NOT NULL,
  payload TEXT NOT NULL,
  first_seen_at TEXT NOT NULL,
  last_seen_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS current_matches_business_date
  ON current_matches(business_date, match_number);
CREATE TABLE IF NOT EXISTS odds_history (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  match_id TEXT NOT NULL,
  collected_at TEXT NOT NULL,
  odds_hash TEXT NOT NULL,
  payload TEXT NOT NULL,
  UNIQUE(match_id, collected_at)
);
CREATE INDEX IF NOT EXISTS odds_history_match_time
  ON odds_history(match_id, collected_at);
"""


def connect_database(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=30)
    connection.executescript(SCHEMA)
    return connection


def save_matches(connection: sqlite3.Connection, matches: Iterable[dict[str, Any]], collected_at: str) -> int:
    count = 0
    with connection:
        for source in matches:
            item = normalized(source, collected_at)
            serialized = json.dumps(item, ensure_ascii=False, separators=(",", ":"))
            connection.execute(
                """INSERT INTO current_matches
                   (match_id,business_date,official_number,match_number,payload,first_seen_at,last_seen_at)
                   VALUES (?,?,?,?,?,?,?)
                   ON CONFLICT(match_id) DO UPDATE SET
                     business_date=excluded.business_date,
                     official_number=excluded.official_number,
                     match_number=excluded.match_number,
                     payload=excluded.payload,
                     last_seen_at=excluded.last_seen_at""",
                (
                    item["matchId"], item["businessDate"], item["officialNumber"],
                    item["matchNumber"], serialized, collected_at, collected_at,
                ),
            )
            odds = json.dumps({"had": item["had"], "hhad": item["hhad"]}, sort_keys=True, separators=(",", ":"))
            odds_hash = hashlib.sha256(odds.encode("utf-8")).hexdigest()
            previous = connection.execute(
                "SELECT odds_hash FROM odds_history WHERE match_id=? ORDER BY id DESC LIMIT 1",
                (item["matchId"],),
            ).fetchone()
            if previous is None or previous[0] != odds_hash:
                connection.execute(
                    "INSERT OR IGNORE INTO odds_history(match_id,collected_at,odds_hash,payload) VALUES (?,?,?,?)",
                    (item["matchId"], collected_at, odds_hash, serialized),
                )
            count += 1
    return count


def export_current(
    connection: sqlite3.Connection,
    output: Path,
    collected_at: str,
    preferred_business_dates: list[str] | None = None,
) -> int:
    business_dates = sorted({date for date in (preferred_business_dates or []) if date})
    if not business_dates:
        row = connection.execute("SELECT MAX(business_date) FROM current_matches").fetchone()
        business_dates = [str(row[0]) if row and row[0] else now_shanghai().date().isoformat()]
    placeholders = ",".join("?" for _ in business_dates)
    rows = connection.execute(
        f"SELECT payload FROM current_matches WHERE business_date IN ({placeholders}) ORDER BY business_date,match_number",
        business_dates,
    ).fetchall()
    matches = [json.loads(row[0]) for row in rows]
    recommendations = build_recommendations(matches, business_dates)
    atomic_json(
        output,
        {
            "source": "中国体育彩票官方接口",
            "businessDate": business_dates[0],
            "businessDates": business_dates,
            "updatedAt": collected_at,
            "count": len(matches),
            "matches": matches,
            "recommendations": recommendations,
        },
    )
    return len(matches)


def save_raw_snapshot(directory: Path, raw: bytes, retention_days: int) -> None:
    now = now_shanghai()
    day_directory = directory / "raw" / now.strftime("%Y-%m-%d")
    day_directory.mkdir(parents=True, exist_ok=True)
    path = day_directory / f"{now.strftime('%H%M%S')}.json.gz"
    with gzip.open(path, "wb") as stream:
        stream.write(raw)
    cutoff = now - timedelta(days=retention_days)
    for old_path in (directory / "raw").glob("*/*.json.gz"):
        with contextlib.suppress(OSError):
            if datetime.fromtimestamp(old_path.stat().st_mtime, SHANGHAI) < cutoff:
                old_path.unlink()


def run_once(args: argparse.Namespace) -> int:
    data_dir = Path(args.data_dir)
    lock_path = data_dir / "collector.lock"
    data_dir.mkdir(parents=True, exist_ok=True)
    with lock_path.open("w") as lock:
        if fcntl is not None:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                logging.info("another collector process is already running")
                return 0
        started_at = utc_iso()
        connection = connect_database(Path(args.database))
        cursor = connection.execute(
            "INSERT INTO collector_runs(started_at,status) VALUES (?,?)", (started_at, "running")
        )
        run_id = cursor.lastrowid
        connection.commit()
        try:
            payload, raw = fetch_payload(args.url, args.timeout, args.retries)
            matches = flatten_matches(payload)
            collected_at = utc_iso()
            live_count = save_matches(connection, matches, collected_at)
            live_business_dates = sorted(
                {str(item.get("businessDate") or "") for item in matches if item.get("businessDate")}
            )
            retained_count = export_current(
                connection, data_dir / "latest.json", collected_at, live_business_dates
            )
            save_raw_snapshot(data_dir, raw, args.retention_days)
            health = {
                "status": "ok", "checkedAt": collected_at, "liveMatchCount": live_count,
                "retainedMatchCount": retained_count, "businessDates": live_business_dates,
                "source": "中国体育彩票官方接口",
            }
            atomic_json(data_dir / "health.json", health)
            with connection:
                connection.execute(
                    "UPDATE collector_runs SET finished_at=?,status=?,match_count=? WHERE id=?",
                    (collected_at, "ok", live_count, run_id),
                )
            logging.info("collection complete: live=%d retained=%d", live_count, retained_count)
            return 0
        except Exception as error:
            finished_at = utc_iso()
            atomic_json(data_dir / "health.json", {"status": "error", "checkedAt": finished_at, "error": str(error)})
            with connection:
                connection.execute(
                    "UPDATE collector_runs SET finished_at=?,status=?,error=? WHERE id=?",
                    (finished_at, "error", str(error), run_id),
                )
            logging.exception("collection failed")
            return 1
        finally:
            connection.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect official China Sporttery football data")
    parser.add_argument("--once", action="store_true", help="run one collection cycle")
    parser.add_argument("--url", default=os.environ.get("SPORTTERY_URL", SPORTTERY_URL))
    parser.add_argument("--data-dir", default=os.environ.get("FOOTBALL_AI_DATA_DIR", "/var/lib/football-ai"))
    parser.add_argument("--database", default=os.environ.get("FOOTBALL_AI_DATABASE", "/var/lib/football-ai/football-ai.sqlite3"))
    parser.add_argument("--timeout", type=float, default=20)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--retention-days", type=int, default=90)
    return parser.parse_args()


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = parse_args()
    if not args.once:
        print("Use --once; systemd starts one safe collection cycle every five minutes.", file=sys.stderr)
        return 2
    return run_once(args)


if __name__ == "__main__":
    raise SystemExit(main())

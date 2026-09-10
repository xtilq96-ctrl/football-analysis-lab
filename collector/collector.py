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
import hmac
import json
import logging
import math
import os
import re
import sqlite3
import sys
import tempfile
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
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
SPORTTERY_RESULTS_URL = (
    "https://webapi.sporttery.cn/gateway/uniform/football/getUniformMatchResultV1.qry"
)
API_FOOTBALL_URL = "https://v3.football.api-sports.io"
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


def push_latest_to_site(
    path: Path,
    url: str,
    auth_token: str,
    relay_secret_file: Path,
    timeout: float,
    retries: int,
) -> None:
    if not url or not auth_token:
        raise RuntimeError("website push is not configured")
    body = path.read_bytes()
    secret = relay_secret_file.read_bytes().strip()
    if len(secret) < 32:
        raise RuntimeError("relay secret is invalid")
    signature = hmac.new(secret, body, hashlib.sha256).hexdigest()
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            request = urllib.request.Request(
                url,
                data=body,
                method="POST",
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "X-Football-Signature": signature,
                    "OAI-Sites-Authorization": f"Bearer {auth_token}",
                    "User-Agent": HEADERS["User-Agent"],
                },
            )
            with urllib.request.urlopen(request, timeout=timeout) as response:
                response_body = json.loads(response.read())
                if response.status != 200 or response_body.get("ok") is not True:
                    raise RuntimeError(f"website ingest returned HTTP {response.status}")
            return
        except (OSError, ValueError, urllib.error.URLError, RuntimeError) as error:
            last_error = error
            if attempt < retries:
                time.sleep(2 ** (attempt - 1))
    raise RuntimeError(f"website push failed after {retries} attempts: {last_error}")


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


def fetch_results_window(
    begin_date: str,
    end_date: str,
    timeout: float,
    retries: int = 3,
) -> list[dict[str, Any]]:
    """Read every page from the official result archive for a date window."""
    params = urllib.parse.urlencode({
        "matchBeginDate": begin_date,
        "matchEndDate": end_date,
        "leagueId": "",
        "pageSize": "100",
        "isFix": "0",
        "matchPage": "1",
        "pcOrWap": "1",
    })
    headers = {**HEADERS, "Referer": "https://www.sporttery.cn/jc/zqsgkj/"}
    results: list[dict[str, Any]] = []
    page = 1
    pages = 1
    while page <= pages:
        last_error: Exception | None = None
        for attempt in range(1, retries + 1):
            url = f"{SPORTTERY_RESULTS_URL}?{params}&pageNo={page}"
            request = urllib.request.Request(url, headers=headers)
            try:
                with urllib.request.urlopen(request, timeout=timeout) as response:
                    payload = json.loads(response.read())
                if payload.get("success") is not True or str(payload.get("errorCode")) != "0":
                    raise RuntimeError("official result endpoint returned an unsuccessful payload")
                value = payload.get("value", {})
                items = value.get("matchResult", [])
                if not isinstance(items, list):
                    raise RuntimeError("official result endpoint payload has an unexpected structure")
                results.extend(item for item in items if isinstance(item, dict))
                pages = max(1, int(value.get("pages") or 1))
                break
            except (OSError, ValueError, urllib.error.URLError, RuntimeError) as error:
                last_error = error
                if attempt < retries:
                    time.sleep(2 ** (attempt - 1))
        else:
            raise RuntimeError(f"result fetch failed after {retries} attempts: {last_error}")
        page += 1
    return results


def fetch_results(timeout: float, retries: int = 3) -> list[dict[str, Any]]:
    now = now_shanghai()
    return fetch_results_window(
        (now - timedelta(days=7)).date().isoformat(),
        now.date().isoformat(),
        timeout,
        retries,
    )


def api_football_request(
    connection: sqlite3.Connection,
    api_key: str,
    endpoint: str,
    params: dict[str, Any],
    ttl: timedelta,
    timeout: float,
    retries: int,
) -> list[dict[str, Any]]:
    """Fetch one API-Football resource with a persistent, quota-friendly cache."""
    normalized_params = {key: str(value) for key, value in params.items() if value not in (None, "")}
    query = urllib.parse.urlencode(sorted(normalized_params.items()))
    cache_key = f"api-football:{endpoint}?{query}"
    now = datetime.now(timezone.utc)
    cached = connection.execute(
        "SELECT payload,expires_at FROM api_cache WHERE cache_key=?", (cache_key,)
    ).fetchone()
    if cached:
        with contextlib.suppress(ValueError):
            if datetime.fromisoformat(cached[1]) > now:
                payload = json.loads(cached[0])
                return payload if isinstance(payload, list) else []

    last_error: Exception | None = None
    url = f"{API_FOOTBALL_URL}/{endpoint}"
    if query:
        url = f"{url}?{query}"
    for attempt in range(1, retries + 1):
        try:
            request = urllib.request.Request(
                url,
                headers={
                    "Accept": "application/json",
                    "User-Agent": HEADERS["User-Agent"],
                    "x-apisports-key": api_key,
                },
            )
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = json.loads(response.read())
            errors = payload.get("errors")
            if errors and errors not in ({}, []):
                category = next(iter(errors), "request") if isinstance(errors, dict) else "request"
                raise RuntimeError(f"API-Football {category} error for {endpoint}")
            items = payload.get("response", [])
            if not isinstance(items, list):
                raise RuntimeError(f"API-Football returned an unexpected {endpoint} payload")
            serialized = json.dumps(items, ensure_ascii=False, separators=(",", ":"))
            with connection:
                connection.execute(
                    """INSERT INTO api_cache(cache_key,payload,fetched_at,expires_at)
                       VALUES (?,?,?,?) ON CONFLICT(cache_key) DO UPDATE SET
                       payload=excluded.payload,fetched_at=excluded.fetched_at,
                       expires_at=excluded.expires_at""",
                    (cache_key, serialized, now.isoformat(), (now + ttl).isoformat()),
                )
            return items
        except (OSError, ValueError, urllib.error.URLError, RuntimeError) as error:
            last_error = error
            if attempt < retries:
                time.sleep(2 ** (attempt - 1))
    if cached:
        logging.warning("using stale API-Football cache for %s: %s", endpoint, last_error)
        payload = json.loads(cached[0])
        return payload if isinstance(payload, list) else []
    raise RuntimeError(f"API-Football fetch failed for {endpoint}: {last_error}")


def parse_kickoff(match: dict[str, Any]) -> datetime | None:
    value = f"{match.get('kickoffDate') or match.get('matchDate') or ''}T{match.get('kickoffTime') or match.get('matchTime') or ''}"
    with contextlib.suppress(ValueError):
        return datetime.fromisoformat(value).replace(tzinfo=SHANGHAI)
    return None


def analysis_schedule(match: dict[str, Any], now: datetime | None = None) -> dict[str, Any]:
    """Create an early-match aware finalization and lock schedule in China time."""
    current = now or now_shanghai()
    kickoff = parse_kickoff(match)
    business_date_text = str(match.get("businessDate") or "")
    try:
        business_date = datetime.fromisoformat(business_date_text).replace(tzinfo=SHANGHAI)
    except ValueError:
        business_date = current.replace(hour=0, minute=0, second=0, microsecond=0)
    global_final = business_date.replace(hour=20, minute=50)
    global_lock = business_date.replace(hour=21, minute=0)
    if kickoff is None:
        return {
            "phase": "时间待确认", "isLocked": False, "isEarlyMatch": False,
            "finalAnalysisAt": global_final.isoformat(), "lockAt": global_lock.isoformat(),
            "minutesToKickoff": None,
        }
    final_at = min(kickoff - timedelta(minutes=90), global_final)
    lock_at = min(kickoff - timedelta(minutes=60), global_lock)
    minutes = int((kickoff - current).total_seconds() // 60)
    if current >= kickoff:
        phase = "已开赛"
    elif current >= lock_at:
        phase = "最终锁定"
    elif current >= final_at:
        phase = "最终分析"
    else:
        phase = "持续更新"
    return {
        "phase": phase,
        "isLocked": current >= lock_at,
        "isEarlyMatch": kickoff.date() == business_date.date() and kickoff.time() < datetime.strptime("21:00", "%H:%M").time(),
        "finalAnalysisAt": final_at.isoformat(),
        "lockAt": lock_at.isoformat(),
        "minutesToKickoff": minutes,
    }


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


def compact_name(value: Any) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", normalized.lower())


def name_acronym(value: Any) -> str:
    words = re.findall(r"[a-z0-9]+", unicodedata.normalize("NFKD", str(value or "")).lower())
    return "".join(word[0] for word in words if word and word not in {"fc", "cf", "sc", "club"})


def team_name_similarity(hints: Iterable[Any], api_name: Any) -> float:
    target = compact_name(api_name)
    acronym = name_acronym(api_name)
    best = 0.0
    for hint_value in hints:
        hint = compact_name(hint_value)
        if not hint:
            continue
        if hint == target or hint == acronym:
            return 1.0
        if len(hint) >= 3 and (hint in target or target in hint):
            best = max(best, 0.9)
        if len(hint) >= 2 and acronym and (hint == acronym or hint in acronym):
            best = max(best, 0.82)
        best = max(best, SequenceMatcher(None, hint, target).ratio())
    return best


def match_api_fixture(match: dict[str, Any], fixtures: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, float]:
    kickoff = parse_kickoff(match)
    if kickoff is None:
        return None, 0.0
    home_hints = (match.get("homeTeamCode"), match.get("homeTeamEn"), match.get("home"))
    away_hints = (match.get("awayTeamCode"), match.get("awayTeamEn"), match.get("away"))
    best_fixture: dict[str, Any] | None = None
    best_score = 0.0
    for fixture in fixtures:
        timestamp = (fixture.get("fixture") or {}).get("timestamp")
        try:
            api_kickoff = datetime.fromtimestamp(int(timestamp), timezone.utc).astimezone(SHANGHAI)
        except (TypeError, ValueError, OSError):
            continue
        difference = abs((api_kickoff - kickoff).total_seconds())
        if difference > 20 * 60:
            continue
        teams = fixture.get("teams") or {}
        home_score = team_name_similarity(home_hints, (teams.get("home") or {}).get("name"))
        away_score = team_name_similarity(away_hints, (teams.get("away") or {}).get("name"))
        time_score = max(0.0, 1 - difference / (20 * 60))
        score = time_score * 0.55 + home_score * 0.225 + away_score * 0.225
        if score > best_score:
            best_fixture, best_score = fixture, score
    return (best_fixture, round(best_score, 3)) if best_score >= 0.72 else (None, round(best_score, 3))


def team_form_summary(fixtures: list[dict[str, Any]], team_id: int, venue: str, kickoff: datetime) -> dict[str, Any]:
    completed: list[dict[str, Any]] = []
    for item in fixtures:
        fixture = item.get("fixture") or {}
        status = (fixture.get("status") or {}).get("short")
        timestamp = fixture.get("timestamp")
        if status not in {"FT", "AET", "PEN"} or timestamp is None:
            continue
        played_at = datetime.fromtimestamp(int(timestamp), timezone.utc).astimezone(SHANGHAI)
        if played_at >= kickoff:
            continue
        item = dict(item)
        item["_playedAt"] = played_at
        completed.append(item)
    completed.sort(key=lambda item: item["_playedAt"], reverse=True)
    recent = completed[:10]
    venue_games = [
        item for item in recent
        if int((((item.get("teams") or {}).get(venue) or {}).get("id") or 0)) == team_id
    ][:5]

    def calculate(items: list[dict[str, Any]]) -> dict[str, Any]:
        wins = draws = losses = goals_for = goals_against = clean_sheets = 0
        form: list[str] = []
        for item in items:
            teams = item.get("teams") or {}
            goals = item.get("goals") or {}
            is_home = int(((teams.get("home") or {}).get("id") or 0)) == team_id
            scored = int(goals.get("home") or 0) if is_home else int(goals.get("away") or 0)
            conceded = int(goals.get("away") or 0) if is_home else int(goals.get("home") or 0)
            goals_for += scored
            goals_against += conceded
            clean_sheets += int(conceded == 0)
            if scored > conceded:
                wins += 1
                form.append("W")
            elif scored == conceded:
                draws += 1
                form.append("D")
            else:
                losses += 1
                form.append("L")
        games = len(items)
        return {
            "matches": games, "wins": wins, "draws": draws, "losses": losses,
            "pointsPerGame": round((wins * 3 + draws) / games, 2) if games else None,
            "goalsForPerGame": round(goals_for / games, 2) if games else None,
            "goalsAgainstPerGame": round(goals_against / games, 2) if games else None,
            "cleanSheetRate": round(clean_sheets / games * 100, 1) if games else None,
            "form": "".join(form),
        }

    summary = calculate(recent)
    summary["venue"] = calculate(venue_games)
    if recent:
        rest_days = max(0.0, (kickoff - recent[0]["_playedAt"]).total_seconds() / 86400)
        summary["restDays"] = round(rest_days, 1)
    else:
        summary["restDays"] = None
    summary["matchesLast14Days"] = sum(
        1 for item in completed if timedelta(0) <= kickoff - item["_playedAt"] <= timedelta(days=14)
    )
    return summary


def form_strength(summary: dict[str, Any]) -> float:
    if not summary.get("matches"):
        return 0.0
    ppg = float(summary.get("pointsPerGame") or 0)
    goal_difference = float(summary.get("goalsForPerGame") or 0) - float(summary.get("goalsAgainstPerGame") or 0)
    clean = float(summary.get("cleanSheetRate") or 0) / 100
    base = ((ppg - 1.5) / 1.5) * 0.45 + math.tanh(goal_difference / 1.5) * 0.35 + (clean - 0.3) * 0.2
    venue = summary.get("venue") or {}
    if venue.get("matches"):
        venue_ppg = float(venue.get("pointsPerGame") or 0)
        venue_goal_difference = float(venue.get("goalsForPerGame") or 0) - float(venue.get("goalsAgainstPerGame") or 0)
        venue_score = ((venue_ppg - 1.5) / 1.5) * 0.6 + math.tanh(venue_goal_difference / 1.5) * 0.4
        base = base * 0.7 + venue_score * 0.3
    return max(-1.0, min(1.0, base))


def absence_summary(items: list[dict[str, Any]], fixture_id: int, team_id: int) -> dict[str, Any]:
    selected = [
        item for item in items
        if int(((item.get("fixture") or {}).get("id") or 0)) == fixture_id
        and int(((item.get("team") or {}).get("id") or 0)) == team_id
    ]
    suspension_words = ("suspend", "red card", "yellow card", "disciplin")
    suspensions = sum(
        1 for item in selected
        if any(word in str((item.get("player") or {}).get("reason") or "").lower() for word in suspension_words)
    )
    return {
        "total": len(selected),
        "injuries": len(selected) - suspensions,
        "suspensions": suspensions,
        "players": [
            {
                "name": str((item.get("player") or {}).get("name") or ""),
                "reason": str((item.get("player") or {}).get("reason") or "未说明"),
            }
            for item in selected[:8]
        ],
    }


def blend_fundamentals(base: dict[str, Any], fundamentals: dict[str, Any]) -> dict[str, Any]:
    market = base.get("probabilities")
    if not isinstance(market, dict) or fundamentals.get("status") not in {"partial", "ready"}:
        return base
    home = fundamentals["home"]
    away = fundamentals["away"]
    delta = (form_strength(home["form"]) - form_strength(away["form"])) * 0.55
    home_rest = home["form"].get("restDays")
    away_rest = away["form"].get("restDays")
    if home_rest is not None and home_rest < 4:
        delta -= 0.05
    if away_rest is not None and away_rest < 4:
        delta += 0.05
    delta += min(0.10, away["absences"]["injuries"] * 0.015 + away["absences"]["suspensions"] * 0.025)
    delta -= min(0.10, home["absences"]["injuries"] * 0.015 + home["absences"]["suspensions"] * 0.025)
    delta = max(-0.28, min(0.28, delta))
    weighted = [
        float(market["home"]) * math.exp(delta),
        float(market["draw"]) * math.exp(-abs(delta) * 0.12),
        float(market["away"]) * math.exp(-delta),
    ]
    total = sum(weighted)
    values = [round(value / total * 100, 2) for value in weighted]
    labels = ["主胜", "平局", "客胜"]
    ordered = sorted(values, reverse=True)
    gap = ordered[0] - ordered[1]
    fundamentals["probabilityAdjustmentPoints"] = {
        "home": round(values[0] - float(market["home"]), 2),
        "draw": round(values[1] - float(market["draw"]), 2),
        "away": round(values[2] - float(market["away"]), 2),
    }
    return {
        **base,
        **score_model(values),
        "modelVersion": (
            "v2-market-official-history"
            if fundamentals.get("source") == "sporttery_history"
            else "v2-market-fundamentals"
        ),
        "marketProbabilities": market,
        "probabilities": dict(zip(("home", "draw", "away"), values)),
        "prediction": labels[values.index(max(values))],
        "confidence": round(max(values), 2),
        "risk": "低风险" if gap >= 25 else "中风险" if gap >= 12 else "高风险",
    }


def build_recommendations(
    matches: list[dict[str, Any]],
    business_dates: list[str],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, dict[str, Any]]]:
    """Build a restrained daily plan that may contain zero, two, three or four legs."""
    result: dict[str, list[dict[str, Any]]] = {}
    decisions: dict[str, dict[str, Any]] = {}
    pick_key = {"主胜": "h", "平局": "d", "客胜": "a"}
    for business_date in business_dates:
        candidates: list[dict[str, Any]] = []
        for item in matches:
            if item.get("businessDate") != business_date:
                continue
            if (item.get("analysisSchedule") or {}).get("phase") == "已开赛":
                continue
            analysis = item.get("analysis") or {}
            prediction = analysis.get("prediction")
            confidence = float(analysis.get("confidence") or 0)
            price = decimal_odds((item.get("had") or {}).get(pick_key.get(prediction)))
            probabilities = analysis.get("probabilities") or {}
            market_probabilities = analysis.get("marketProbabilities") or probabilities
            probability_key = {"主胜": "home", "平局": "draw", "客胜": "away"}.get(prediction)
            market_probability = float(market_probabilities.get(probability_key) or 0) if probability_key else 0
            edge = confidence - market_probability
            value_index = confidence / 100 * price if price is not None else 0
            risk = str(analysis.get("risk") or "待评估")
            if (
                prediction not in pick_key or confidence < 45 or price is None
                or risk == "高风险" or edge < 1 or value_index < 1.01
            ):
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
                "edge": round(edge, 2),
                "valueIndex": round(value_index, 3),
                "risk": risk,
                "isLocked": bool((item.get("analysisSchedule") or {}).get("isLocked")),
                "quality": confidence + max(-3.0, min(8.0, edge)) - float(analysis.get("marketMargin") or 0) * 0.35,
            })
        candidates.sort(key=lambda item: (item["quality"], item["probability"]), reverse=True)

        strong = [item for item in candidates if item["probability"] >= 54]
        solid = [item for item in candidates if item["probability"] >= 50]
        leg_count = 0
        threshold = 0.0
        if len(strong) >= 4:
            best_four_probability = math.prod(item["probability"] / 100 for item in strong[:4]) * 100
            if best_four_probability >= 10:
                leg_count, threshold = 4, 10
        if leg_count == 0 and len(strong) >= 3:
            best_three_probability = math.prod(item["probability"] / 100 for item in strong[:3]) * 100
            if best_three_probability >= 17:
                leg_count, threshold = 3, 17
        if leg_count == 0 and len(solid) >= 2:
            best_two_probability = math.prod(item["probability"] / 100 for item in solid[:2]) * 100
            if best_two_probability >= 27:
                leg_count, threshold = 2, 27

        if leg_count == 0:
            result[business_date] = []
            decisions[business_date] = {
                "status": "no_pick", "legCount": 0, "candidateCount": len(candidates),
                "reason": "可用场次、单场概率或组合概率未同时达到安全门槛，系统今日不强行推荐。",
                "rulesVersion": "dynamic-combo-v1",
            }
            continue

        from itertools import combinations

        pool = strong if leg_count >= 3 else solid
        combinations_ranked: list[dict[str, Any]] = []
        for legs_tuple in combinations(pool[:8], leg_count):
            leagues = {leg["league"] for leg in legs_tuple}
            if leg_count >= 3 and len(leagues) < 2:
                continue
            combined_probability = math.prod(leg["probability"] / 100 for leg in legs_tuple) * 100
            if combined_probability < threshold:
                continue
            combined_odds = math.prod(leg["odds"] for leg in legs_tuple)
            average_edge = sum(leg["edge"] for leg in legs_tuple) / leg_count
            diversity = len(leagues) / leg_count
            score = combined_probability + average_edge * 0.8 + diversity * 3
            combinations_ranked.append({
                "type": f"{leg_count}串1", "legCount": leg_count,
                "legs": [
                    {key: value for key, value in leg.items() if key not in {"quality", "isLocked"}}
                    for leg in legs_tuple
                ],
                "combinedProbability": round(combined_probability, 2),
                "combinedOdds": round(combined_odds, 2),
                "averageEdge": round(average_edge, 2),
                "level": "相对稳健" if combined_probability >= threshold * 1.35 else "谨慎观察",
                "isLocked": any(leg["isLocked"] for leg in legs_tuple),
                "basis": f"{leg_count}场均达到概率与正向价值门槛，覆盖{len(leagues)}个联赛；组合概率不低于{threshold:.0f}%",
                "_score": score,
            })
        combinations_ranked.sort(key=lambda item: item["_score"], reverse=True)
        selected: list[dict[str, Any]] = []
        seen: set[tuple[str, ...]] = set()
        for combination in combinations_ranked:
            identity = tuple(sorted(leg["matchId"] for leg in combination["legs"]))
            if identity in seen:
                continue
            seen.add(identity)
            combination.pop("_score", None)
            selected.append(combination)
            if len(selected) == 3:
                break
        result[business_date] = selected
        decisions[business_date] = {
            "status": "recommended" if selected else "no_pick",
            "legCount": leg_count if selected else 0,
            "candidateCount": len(candidates),
            "reason": (
                f"系统综合单场概率、风险、概率优势和联赛相关性，自动选择{leg_count}串1。"
                if selected else "候选场次存在相关性集中或组合概率不足，系统今日不推荐。"
            ),
            "rulesVersion": "dynamic-combo-v1",
        }
    return result, decisions


def official_number(match: dict[str, Any]) -> str:
    if match.get("matchNumStr"):
        return str(match["matchNumStr"])
    number = int(match.get("matchNum") or 0) % 1000
    return f"{match.get('matchWeek', '')}{number:03d}"


def normalized(match: dict[str, Any], collected_at: str) -> dict[str, Any]:
    item = {
        "matchId": str(match["matchId"]),
        "businessDate": str(match.get("businessDate") or ""),
        "officialNumber": official_number(match),
        "matchNumber": int(match.get("matchNum") or 0),
        "league": str(match.get("leagueAllName") or ""),
        "home": str(match.get("homeTeamAllName") or ""),
        "away": str(match.get("awayTeamAllName") or ""),
        "homeTeamId": int(match.get("homeTeamId") or 0),
        "awayTeamId": int(match.get("awayTeamId") or 0),
        "homeTeamCode": str(match.get("homeTeamCode") or ""),
        "awayTeamCode": str(match.get("awayTeamCode") or ""),
        "homeTeamEn": str(match.get("homeTeamAbbEnName") or ""),
        "awayTeamEn": str(match.get("awayTeamAbbEnName") or ""),
        "kickoffDate": str(match.get("matchDate") or ""),
        "kickoffTime": str(match.get("matchTime") or ""),
        "saleStatus": str(match.get("sellStatus") or ""),
        "had": match.get("had"),
        "hhad": match.get("hhad"),
        "analysis": market_analysis(match),
        "collectedAt": collected_at,
    }
    item["analysisSchedule"] = analysis_schedule(item)
    return item


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
CREATE TABLE IF NOT EXISTS api_cache (
  cache_key TEXT PRIMARY KEY,
  payload TEXT NOT NULL,
  fetched_at TEXT NOT NULL,
  expires_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS collector_state (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS official_match_history (
  match_id TEXT PRIMARY KEY,
  match_date TEXT NOT NULL,
  league_id INTEGER NOT NULL DEFAULT 0,
  league_name TEXT NOT NULL,
  home_team_id INTEGER NOT NULL,
  away_team_id INTEGER NOT NULL,
  home_team_name TEXT NOT NULL,
  away_team_name TEXT NOT NULL,
  home_goals INTEGER NOT NULL,
  away_goals INTEGER NOT NULL,
  payload TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS official_history_home_date
  ON official_match_history(home_team_id,match_date);
CREATE INDEX IF NOT EXISTS official_history_away_date
  ON official_match_history(away_team_id,match_date);
CREATE TABLE IF NOT EXISTS locked_predictions (
  match_id TEXT PRIMARY KEY,
  payload TEXT NOT NULL,
  locked_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS match_results (
  match_id TEXT PRIMARY KEY,
  full_time_score TEXT NOT NULL,
  half_time_score TEXT,
  home_goals INTEGER NOT NULL,
  away_goals INTEGER NOT NULL,
  actual_outcome TEXT NOT NULL,
  payload TEXT NOT NULL,
  settled_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS prediction_settlements (
  match_id TEXT PRIMARY KEY,
  predicted_outcome TEXT,
  predicted_score TEXT,
  predicted_total_goals TEXT,
  predicted_over_under TEXT,
  actual_outcome TEXT NOT NULL,
  actual_score TEXT NOT NULL,
  actual_total_goals INTEGER NOT NULL,
  outcome_hit INTEGER,
  score_hit INTEGER,
  total_goals_hit INTEGER,
  over_under_hit INTEGER,
  evaluation_payload TEXT,
  settled_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS two_leg_recommendations (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  business_date TEXT NOT NULL,
  recommendation_key TEXT NOT NULL,
  payload TEXT NOT NULL,
  created_at TEXT NOT NULL,
  UNIQUE(business_date, recommendation_key)
);
CREATE TABLE IF NOT EXISTS two_leg_settlements (
  recommendation_id INTEGER PRIMARY KEY,
  hit INTEGER NOT NULL,
  settled_at TEXT NOT NULL,
  FOREIGN KEY(recommendation_id) REFERENCES two_leg_recommendations(id)
);
"""


def connect_database(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=30)
    connection.executescript(SCHEMA)
    columns = {row[1] for row in connection.execute("PRAGMA table_info(prediction_settlements)")}
    if "evaluation_payload" not in columns:
        connection.execute("ALTER TABLE prediction_settlements ADD COLUMN evaluation_payload TEXT")
        connection.commit()
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


def save_official_history(
    connection: sqlite3.Connection,
    results: Iterable[dict[str, Any]],
    updated_at: str,
) -> int:
    """Persist completed official results as the free long-term form dataset."""
    count = 0
    with connection:
        for result in results:
            score = str(result.get("sectionsNo999") or "")
            if str(result.get("matchResultStatus")) != "2" or ":" not in score:
                continue
            try:
                home_goals, away_goals = (int(value) for value in score.split(":", 1))
                home_team_id = int(result.get("homeTeamId") or 0)
                away_team_id = int(result.get("awayTeamId") or 0)
            except (TypeError, ValueError):
                continue
            match_id = str(result.get("matchId") or "")
            match_date = str(result.get("matchDate") or "")
            if not match_id or not match_date or not home_team_id or not away_team_id:
                continue
            connection.execute(
                """INSERT INTO official_match_history
                   (match_id,match_date,league_id,league_name,home_team_id,away_team_id,
                    home_team_name,away_team_name,home_goals,away_goals,payload,updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(match_id) DO UPDATE SET
                     match_date=excluded.match_date,league_id=excluded.league_id,
                     league_name=excluded.league_name,home_team_id=excluded.home_team_id,
                     away_team_id=excluded.away_team_id,home_team_name=excluded.home_team_name,
                     away_team_name=excluded.away_team_name,home_goals=excluded.home_goals,
                     away_goals=excluded.away_goals,payload=excluded.payload,
                     updated_at=excluded.updated_at""",
                (
                    match_id, match_date, int(result.get("leagueId") or 0),
                    str(result.get("leagueName") or ""), home_team_id, away_team_id,
                    str(result.get("allHomeTeam") or result.get("homeTeam") or ""),
                    str(result.get("allAwayTeam") or result.get("awayTeam") or ""),
                    home_goals, away_goals,
                    json.dumps(result, ensure_ascii=False, separators=(",", ":")), updated_at,
                ),
            )
            count += 1
    return count


def sync_official_history(
    connection: sqlite3.Connection,
    timeout: float,
    retries: int,
    lookback_days: int = 120,
) -> tuple[list[dict[str, Any]], int, bool]:
    """Refresh seven days each run and rebuild 120 days at most once per day."""
    now = now_shanghai()
    state = connection.execute(
        "SELECT value FROM collector_state WHERE key='official_history_full_sync_at'"
    ).fetchone()
    full_sync = True
    if state:
        with contextlib.suppress(ValueError):
            full_sync = datetime.fromisoformat(state[0]) < datetime.now(timezone.utc) - timedelta(hours=24)
    begin = now - timedelta(days=lookback_days if full_sync else 7)
    results: list[dict[str, Any]] = []
    cursor = begin.date()
    end = now.date()
    while cursor <= end:
        chunk_end = min(cursor + timedelta(days=29), end)
        results.extend(fetch_results_window(
            cursor.isoformat(), chunk_end.isoformat(), timeout, retries
        ))
        cursor = chunk_end + timedelta(days=1)
    saved = save_official_history(connection, results, utc_iso())
    if full_sync:
        with connection:
            connection.execute(
                """INSERT INTO collector_state(key,value) VALUES ('official_history_full_sync_at',?)
                   ON CONFLICT(key) DO UPDATE SET value=excluded.value""",
                (datetime.now(timezone.utc).isoformat(),),
            )
    return results, saved, full_sync


def official_history_form_summary(
    connection: sqlite3.Connection,
    team_id: int,
    venue: str,
    kickoff: datetime,
) -> dict[str, Any]:
    rows = connection.execute(
        """SELECT match_date,home_team_id,away_team_id,home_goals,away_goals
           FROM official_match_history
           WHERE (home_team_id=? OR away_team_id=?) AND match_date < ?
           ORDER BY match_date DESC,match_id DESC LIMIT 40""",
        (team_id, team_id, kickoff.date().isoformat()),
    ).fetchall()

    def calculate(items: list[tuple[Any, ...]]) -> dict[str, Any]:
        wins = draws = losses = goals_for = goals_against = clean_sheets = 0
        form: list[str] = []
        for _date, home_id, _away_id, home_goals, away_goals in items:
            is_home = int(home_id) == team_id
            scored = int(home_goals) if is_home else int(away_goals)
            conceded = int(away_goals) if is_home else int(home_goals)
            goals_for += scored
            goals_against += conceded
            clean_sheets += int(conceded == 0)
            if scored > conceded:
                wins += 1
                form.append("W")
            elif scored == conceded:
                draws += 1
                form.append("D")
            else:
                losses += 1
                form.append("L")
        games = len(items)
        return {
            "matches": games, "wins": wins, "draws": draws, "losses": losses,
            "pointsPerGame": round((wins * 3 + draws) / games, 2) if games else None,
            "goalsForPerGame": round(goals_for / games, 2) if games else None,
            "goalsAgainstPerGame": round(goals_against / games, 2) if games else None,
            "cleanSheetRate": round(clean_sheets / games * 100, 1) if games else None,
            "form": "".join(form),
        }

    recent = rows[:10]
    venue_index = 1 if venue == "home" else 2
    venue_games = [row for row in recent if int(row[venue_index]) == team_id][:5]
    summary = calculate(recent)
    summary["venue"] = calculate(venue_games)
    if recent:
        last_date = datetime.fromisoformat(str(recent[0][0])).replace(tzinfo=SHANGHAI)
        summary["restDays"] = max(0, (kickoff.date() - last_date.date()).days)
    else:
        summary["restDays"] = None
    summary["matchesLast14Days"] = sum(
        1 for row in rows
        if 0 <= (kickoff.date() - datetime.fromisoformat(str(row[0])).date()).days <= 14
    )
    return summary


def official_history_fundamentals(
    connection: sqlite3.Connection,
    item: dict[str, Any],
    collected_at: str,
) -> dict[str, Any]:
    kickoff = parse_kickoff(item) or now_shanghai()
    home_id = int(item.get("homeTeamId") or 0)
    away_id = int(item.get("awayTeamId") or 0)
    home_form = official_history_form_summary(connection, home_id, "home", kickoff) if home_id else official_history_form_summary(connection, -1, "home", kickoff)
    away_form = official_history_form_summary(connection, away_id, "away", kickoff) if away_id else official_history_form_summary(connection, -1, "away", kickoff)
    ready_sides = int(bool(home_form.get("matches"))) + int(bool(away_form.get("matches")))

    def team_payload(team_id: int, name: str, form: dict[str, Any]) -> dict[str, Any]:
        return {
            "teamId": team_id, "apiName": name, "form": form,
            "absences": {
                "total": 0, "injuries": 0, "suspensions": 0, "players": [],
                "available": False,
            },
            "lineup": {
                "confirmed": False, "formation": None, "startingCount": 0,
                "available": False,
            },
        }

    return {
        "status": "partial" if ready_sides else "unmatched",
        "coverage": 4 if ready_sides == 2 else 2 if ready_sides == 1 else 0,
        "source": "sporttery_history",
        "sourceLabel": "中国体彩官方历史赛果",
        "dataUpdatedAt": collected_at,
        "message": (
            "已使用体彩官方历史样本；伤停和首发等待专业数据源"
            if ready_sides else "体彩历史样本不足，继续使用市场概率"
        ),
        "home": team_payload(home_id, str(item.get("home") or ""), home_form),
        "away": team_payload(away_id, str(item.get("away") or ""), away_form),
    }


def enrich_fundamentals(
    connection: sqlite3.Connection,
    api_key: str,
    source_matches: list[dict[str, Any]],
    collected_at: str,
    timeout: float,
    retries: int,
) -> dict[str, int]:
    """Attach API-Football fundamentals and freeze each prediction at its deadline."""
    if not api_key:
        enriched_count = 0
        with connection:
            rows = connection.execute("SELECT match_id,payload FROM current_matches").fetchall()
            for match_id, payload in rows:
                item = json.loads(payload)
                item["analysisSchedule"] = analysis_schedule(item)
                locked = connection.execute(
                    "SELECT payload FROM locked_predictions WHERE match_id=?", (match_id,)
                ).fetchone()
                if locked:
                    frozen = json.loads(locked[0])
                    item["analysis"] = frozen.get("analysis", item["analysis"])
                    item["fundamentals"] = frozen.get("fundamentals")
                else:
                    fundamentals = official_history_fundamentals(connection, item, collected_at)
                    item["analysis"] = blend_fundamentals(item["analysis"], fundamentals)
                    item["fundamentals"] = fundamentals
                    enriched_count += int(fundamentals["coverage"] == 4)
                    if item["analysisSchedule"]["isLocked"]:
                        frozen = {"analysis": item["analysis"], "fundamentals": fundamentals}
                        connection.execute(
                            "INSERT OR IGNORE INTO locked_predictions(match_id,payload,locked_at) VALUES (?,?,?)",
                            (match_id, json.dumps(frozen, ensure_ascii=False, separators=(",", ":")), collected_at),
                        )
                connection.execute(
                    "UPDATE current_matches SET payload=? WHERE match_id=?",
                    (json.dumps(item, ensure_ascii=False, separators=(",", ":")), match_id),
                )
        return {"matched": enriched_count, "enriched": enriched_count, "lineups": 0}

    normalized_by_id = {
        str(source["matchId"]): normalized(source, collected_at) for source in source_matches
    }
    dates = sorted({item["kickoffDate"] for item in normalized_by_id.values() if item.get("kickoffDate")})
    fixtures_by_date: dict[str, list[dict[str, Any]]] = {}
    for date in dates:
        fixtures_by_date[date] = api_football_request(
            connection, api_key, "fixtures", {"date": date, "timezone": "Asia/Shanghai"},
            timedelta(hours=6), timeout, retries,
        )

    mapped: dict[str, tuple[dict[str, Any], float]] = {}
    for match_id, item in normalized_by_id.items():
        fixture, confidence = match_api_fixture(item, fixtures_by_date.get(item["kickoffDate"], []))
        if fixture:
            mapped[match_id] = (fixture, confidence)

    histories: dict[int, list[dict[str, Any]]] = {}
    for fixture, _confidence in mapped.values():
        teams = fixture.get("teams") or {}
        for side in ("home", "away"):
            team_id = int(((teams.get(side) or {}).get("id") or 0))
            if team_id and team_id not in histories:
                histories[team_id] = api_football_request(
                    connection, api_key, "fixtures", {"team": team_id, "last": 10, "timezone": "Asia/Shanghai"},
                    timedelta(hours=24), timeout, retries,
                )

    injuries_by_date: dict[str, list[dict[str, Any]]] = {}
    for date in dates:
        injuries_by_date[date] = api_football_request(
            connection, api_key, "injuries", {"date": date, "timezone": "Asia/Shanghai"},
            timedelta(hours=4), timeout, retries,
        )

    now = now_shanghai()
    detail_candidates: list[int] = []
    for match_id, (fixture, _confidence) in mapped.items():
        schedule_match = normalized_by_id[match_id]
        kickoff = parse_kickoff(schedule_match)
        fixture_id = int(((fixture.get("fixture") or {}).get("id") or 0))
        if kickoff and fixture_id and timedelta(minutes=-15) <= kickoff - now <= timedelta(hours=3):
            detail_candidates.append(fixture_id)
    details: dict[int, dict[str, Any]] = {}
    for start in range(0, len(detail_candidates), 20):
        ids = "-".join(str(value) for value in detail_candidates[start:start + 20])
        for item in api_football_request(
            connection, api_key, "fixtures", {"ids": ids, "timezone": "Asia/Shanghai"},
            timedelta(minutes=30), timeout, retries,
        ):
            fixture_id = int(((item.get("fixture") or {}).get("id") or 0))
            if fixture_id:
                details[fixture_id] = item

    enriched_count = lineup_count = 0
    with connection:
        for match_id, item in normalized_by_id.items():
            schedule = analysis_schedule(item, now)
            item["analysisSchedule"] = schedule
            mapping = mapped.get(match_id)
            if not mapping:
                fundamentals = official_history_fundamentals(connection, item, collected_at)
                item["analysis"] = blend_fundamentals(item["analysis"], fundamentals)
                item["fundamentals"] = fundamentals
                enriched_count += int(fundamentals["coverage"] == 4)
            else:
                fixture, confidence = mapping
                fixture_meta = fixture.get("fixture") or {}
                teams = fixture.get("teams") or {}
                fixture_id = int(fixture_meta.get("id") or 0)
                home_team = teams.get("home") or {}
                away_team = teams.get("away") or {}
                home_id = int(home_team.get("id") or 0)
                away_id = int(away_team.get("id") or 0)
                kickoff = parse_kickoff(item) or now
                home_form = team_form_summary(histories.get(home_id, []), home_id, "home", kickoff)
                away_form = team_form_summary(histories.get(away_id, []), away_id, "away", kickoff)
                injury_items = injuries_by_date.get(item["kickoffDate"], [])
                home_absences = absence_summary(injury_items, fixture_id, home_id)
                away_absences = absence_summary(injury_items, fixture_id, away_id)
                lineups = (details.get(fixture_id) or {}).get("lineups") or []
                lineup_by_team = {
                    int(((lineup.get("team") or {}).get("id") or 0)): lineup for lineup in lineups
                }
                home_lineup = lineup_by_team.get(home_id) or {}
                away_lineup = lineup_by_team.get(away_id) or {}
                lineup_confirmed = bool(home_lineup.get("startXI") and away_lineup.get("startXI"))
                lineup_count += int(lineup_confirmed)
                history_ready = bool(home_form.get("matches") and away_form.get("matches"))
                coverage = (4 if history_ready else 0) + 1 + int(lineup_confirmed)
                fundamentals = {
                    "status": "ready" if coverage == 6 else "partial",
                    "coverage": coverage,
                    "source": "api_football",
                    "sourceLabel": "API-Football 专业比赛数据",
                    "mappingConfidence": confidence,
                    "fixtureId": fixture_id,
                    "dataUpdatedAt": collected_at,
                    "home": {
                        "teamId": home_id, "apiName": str(home_team.get("name") or ""),
                        "form": home_form, "absences": home_absences,
                        "lineup": {
                            "confirmed": bool(home_lineup.get("startXI")),
                            "formation": home_lineup.get("formation"),
                            "startingCount": len(home_lineup.get("startXI") or []),
                        },
                    },
                    "away": {
                        "teamId": away_id, "apiName": str(away_team.get("name") or ""),
                        "form": away_form, "absences": away_absences,
                        "lineup": {
                            "confirmed": bool(away_lineup.get("startXI")),
                            "formation": away_lineup.get("formation"),
                            "startingCount": len(away_lineup.get("startXI") or []),
                        },
                    },
                }
                item["analysis"] = blend_fundamentals(item["analysis"], fundamentals)
                item["fundamentals"] = fundamentals
                enriched_count += int(history_ready)

            locked = connection.execute(
                "SELECT payload FROM locked_predictions WHERE match_id=?", (match_id,)
            ).fetchone()
            if locked:
                frozen = json.loads(locked[0])
                item["analysis"] = frozen.get("analysis", item["analysis"])
                item["fundamentals"] = frozen.get("fundamentals", item.get("fundamentals"))
            elif schedule["isLocked"]:
                frozen = {"analysis": item["analysis"], "fundamentals": item.get("fundamentals")}
                connection.execute(
                    "INSERT INTO locked_predictions(match_id,payload,locked_at) VALUES (?,?,?)",
                    (match_id, json.dumps(frozen, ensure_ascii=False, separators=(",", ":")), collected_at),
                )
            connection.execute(
                "UPDATE current_matches SET payload=? WHERE match_id=?",
                (json.dumps(item, ensure_ascii=False, separators=(",", ":")), match_id),
            )
    return {"matched": len(mapped), "enriched": enriched_count, "lineups": lineup_count}


def settle_match_results(
    connection: sqlite3.Connection,
    official_results: list[dict[str, Any]],
    settled_at: str,
) -> tuple[int, int]:
    completed = settled = 0
    with connection:
        for result in official_results:
            match_id = str(result.get("matchId") or "")
            score = str(result.get("sectionsNo999") or "")
            if str(result.get("matchResultStatus")) != "2" or ":" not in score:
                continue
            try:
                home_goals, away_goals = (int(value) for value in score.split(":", 1))
            except ValueError:
                continue
            completed += 1
            actual_outcome = "主胜" if home_goals > away_goals else "平局" if home_goals == away_goals else "客胜"
            display_score = f"{home_goals}-{away_goals}"
            result_payload = json.dumps(result, ensure_ascii=False, separators=(",", ":"))
            connection.execute(
                """INSERT INTO match_results
                   (match_id,full_time_score,half_time_score,home_goals,away_goals,actual_outcome,payload,settled_at)
                   VALUES (?,?,?,?,?,?,?,?)
                   ON CONFLICT(match_id) DO UPDATE SET
                     full_time_score=excluded.full_time_score,
                     half_time_score=excluded.half_time_score,
                     home_goals=excluded.home_goals,
                     away_goals=excluded.away_goals,
                     actual_outcome=excluded.actual_outcome,
                     payload=excluded.payload,
                     settled_at=excluded.settled_at""",
                (
                    match_id, display_score, str(result.get("sectionsNo1") or ""),
                    home_goals, away_goals, actual_outcome, result_payload, settled_at,
                ),
            )
            prediction_row = connection.execute(
                "SELECT payload FROM current_matches WHERE match_id=?", (match_id,)
            ).fetchone()
            if prediction_row is None:
                continue
            prediction = json.loads(prediction_row[0])
            analysis = prediction.get("analysis") or {}
            predicted_outcome = analysis.get("prediction")
            predicted_score = analysis.get("predictedScore")
            predicted_total = analysis.get("predictedTotalGoals")
            over_probability = analysis.get("over25Probability")
            under_probability = analysis.get("under25Probability")
            predicted_over_under = None
            if over_probability is not None and under_probability is not None:
                predicted_over_under = "大2.5" if float(over_probability) >= float(under_probability) else "小2.5"
            actual_total = home_goals + away_goals
            total_hit = None
            if predicted_total == "7+":
                total_hit = int(actual_total >= 7)
            elif str(predicted_total).isdigit():
                total_hit = int(actual_total == int(predicted_total))
            over_under_hit = None
            if predicted_over_under:
                over_under_hit = int(
                    (predicted_over_under == "大2.5" and actual_total >= 3)
                    or (predicted_over_under == "小2.5" and actual_total <= 2)
                )
            probabilities = analysis.get("probabilities") or {}
            probability_values = [
                float(probabilities.get(key) or 0) / 100 for key in ("home", "draw", "away")
            ]
            actual_index = {"主胜": 0, "平局": 1, "客胜": 2}[actual_outcome]
            probability_total = sum(probability_values)
            brier_score = log_loss = None
            if 0.99 <= probability_total <= 1.01:
                brier_score = sum(
                    (probability - (1.0 if index == actual_index else 0.0)) ** 2
                    for index, probability in enumerate(probability_values)
                ) / 3
                log_loss = -math.log(max(0.000001, probability_values[actual_index]))
            evaluation_payload = json.dumps({
                "businessDate": prediction.get("businessDate"),
                "officialNumber": prediction.get("officialNumber"),
                "modelVersion": analysis.get("modelVersion"),
                "probabilities": probabilities or None,
                "confidence": analysis.get("confidence"),
                "brierScore": round(brier_score, 4) if brier_score is not None else None,
                "logLoss": round(log_loss, 4) if log_loss is not None else None,
            }, ensure_ascii=False, separators=(",", ":"))
            connection.execute(
                """INSERT INTO prediction_settlements
                   (match_id,predicted_outcome,predicted_score,predicted_total_goals,predicted_over_under,
                    actual_outcome,actual_score,actual_total_goals,outcome_hit,score_hit,total_goals_hit,
                    over_under_hit,evaluation_payload,settled_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(match_id) DO UPDATE SET
                     actual_outcome=excluded.actual_outcome,
                     actual_score=excluded.actual_score,
                     actual_total_goals=excluded.actual_total_goals,
                     outcome_hit=excluded.outcome_hit,
                     score_hit=excluded.score_hit,
                     total_goals_hit=excluded.total_goals_hit,
                     over_under_hit=excluded.over_under_hit,
                     evaluation_payload=COALESCE(prediction_settlements.evaluation_payload,excluded.evaluation_payload),
                     settled_at=excluded.settled_at""",
                (
                    match_id, predicted_outcome, predicted_score, predicted_total, predicted_over_under,
                    actual_outcome, display_score, actual_total,
                    int(predicted_outcome == actual_outcome) if predicted_outcome else None,
                    int(predicted_score == display_score) if predicted_score else None,
                    total_hit, over_under_hit, evaluation_payload, settled_at,
                ),
            )
            settled += 1
    return completed, settled


def save_combo_recommendations(
    connection: sqlite3.Connection,
    recommendations: dict[str, list[dict[str, Any]]],
    created_at: str,
) -> None:
    with connection:
        for business_date, items in recommendations.items():
            for item in items:
                if not item.get("isLocked"):
                    continue
                identity = "|".join(
                    sorted(f"{leg['matchId']}:{leg['pick']}" for leg in item["legs"])
                )
                identity = f"dynamic-v1:{len(item['legs'])}:{identity}"
                connection.execute(
                    """INSERT OR IGNORE INTO two_leg_recommendations
                       (business_date,recommendation_key,payload,created_at) VALUES (?,?,?,?)""",
                    (
                        business_date, identity,
                        json.dumps(item, ensure_ascii=False, separators=(",", ":")), created_at,
                    ),
                )


def settle_combo_recommendations(connection: sqlite3.Connection, settled_at: str) -> int:
    pending = connection.execute(
        """SELECT r.id,r.payload FROM two_leg_recommendations r
           LEFT JOIN two_leg_settlements s ON s.recommendation_id=r.id
           WHERE s.recommendation_id IS NULL"""
    ).fetchall()
    count = 0
    with connection:
        for recommendation_id, payload in pending:
            item = json.loads(payload)
            leg_hits: list[bool] = []
            complete = True
            for leg in item.get("legs", []):
                row = connection.execute(
                    "SELECT actual_outcome FROM prediction_settlements WHERE match_id=?",
                    (str(leg.get("matchId")),),
                ).fetchone()
                if row is None:
                    complete = False
                    break
                leg_hits.append(row[0] == leg.get("pick"))
            if complete and 2 <= len(leg_hits) <= 4:
                connection.execute(
                    "INSERT INTO two_leg_settlements(recommendation_id,hit,settled_at) VALUES (?,?,?)",
                    (recommendation_id, int(all(leg_hits)), settled_at),
                )
                count += 1
    return count


def performance_summary(connection: sqlite3.Connection) -> dict[str, Any]:
    row = connection.execute(
        """SELECT COUNT(*),COALESCE(SUM(outcome_hit),0),COALESCE(SUM(score_hit),0),
                  COALESCE(SUM(total_goals_hit),0),COALESCE(SUM(over_under_hit),0)
           FROM prediction_settlements"""
    ).fetchone()
    combo_rows = connection.execute(
        """SELECT r.payload,s.hit FROM two_leg_recommendations r
           JOIN two_leg_settlements s ON s.recommendation_id=r.id"""
    ).fetchall()
    total = int(row[0])
    combo_stats: dict[int, dict[str, int]] = {2: {"settled": 0, "hits": 0}, 3: {"settled": 0, "hits": 0}, 4: {"settled": 0, "hits": 0}}
    for payload, hit in combo_rows:
        with contextlib.suppress(ValueError, TypeError):
            leg_count = len((json.loads(payload) or {}).get("legs") or [])
            if leg_count in combo_stats:
                combo_stats[leg_count]["settled"] += 1
                combo_stats[leg_count]["hits"] += int(hit)
    combo_total = sum(item["settled"] for item in combo_stats.values())
    combo_hits = sum(item["hits"] for item in combo_stats.values())
    rate = lambda hits, sample: round(hits / sample * 100, 1) if sample else None
    evaluation_rows = connection.execute(
        """SELECT outcome_hit,evaluation_payload FROM prediction_settlements
           WHERE evaluation_payload IS NOT NULL ORDER BY settled_at DESC"""
    ).fetchall()

    def probability_metrics(rows: list[tuple[Any, Any]]) -> dict[str, Any]:
        parsed: list[tuple[int, dict[str, Any]]] = []
        for hit, payload in rows:
            with contextlib.suppress(ValueError, TypeError):
                item = json.loads(payload)
                if item.get("brierScore") is not None and item.get("confidence") is not None:
                    parsed.append((int(hit), item))
        if not parsed:
            return {"sampleSize": 0, "outcomeHitRate": None, "brierScore": None, "logLoss": None}
        return {
            "sampleSize": len(parsed),
            "outcomeHitRate": rate(sum(hit for hit, _item in parsed), len(parsed)),
            "brierScore": round(sum(float(item["brierScore"]) for _hit, item in parsed) / len(parsed), 4),
            "logLoss": round(sum(float(item["logLoss"]) for _hit, item in parsed) / len(parsed), 4),
        }

    buckets = [(0, 50, "低于50%"), (50, 60, "50%～59%"), (60, 70, "60%～69%"), (70, 101, "70%以上")]
    calibration: list[dict[str, Any]] = []
    for lower, upper, label in buckets:
        selected: list[tuple[int, float]] = []
        for hit, payload in evaluation_rows:
            with contextlib.suppress(ValueError, TypeError):
                confidence = float(json.loads(payload).get("confidence"))
                if lower <= confidence < upper:
                    selected.append((int(hit), confidence))
        if selected:
            average_confidence = sum(value for _hit, value in selected) / len(selected)
            actual_hit_rate = sum(hit for hit, _value in selected) / len(selected) * 100
            calibration.append({
                "label": label, "sampleSize": len(selected),
                "averageConfidence": round(average_confidence, 1),
                "actualHitRate": round(actual_hit_rate, 1),
                "gap": round(actual_hit_rate - average_confidence, 1),
            })
    calibration_error = (
        round(sum(abs(item["gap"]) * item["sampleSize"] for item in calibration) / sum(item["sampleSize"] for item in calibration), 1)
        if calibration else None
    )
    all_probability = probability_metrics(evaluation_rows)
    recent_probability = probability_metrics(evaluation_rows[:30])
    return {
        "settledMatches": total,
        "outcomeHits": int(row[1]),
        "outcomeHitRate": rate(int(row[1]), total),
        "exactScoreHits": int(row[2]),
        "exactScoreHitRate": rate(int(row[2]), total),
        "totalGoalsHits": int(row[3]),
        "totalGoalsHitRate": rate(int(row[3]), total),
        "overUnderHits": int(row[4]),
        "overUnderHitRate": rate(int(row[4]), total),
        "settledTwoLegs": combo_stats[2]["settled"],
        "twoLegHits": combo_stats[2]["hits"],
        "twoLegHitRate": rate(combo_stats[2]["hits"], combo_stats[2]["settled"]),
        "settledCombinations": combo_total,
        "combinationHits": combo_hits,
        "combinationHitRate": rate(combo_hits, combo_total),
        "combinationStats": [
            {"legCount": leg_count, **values, "hitRate": rate(values["hits"], values["settled"])}
            for leg_count, values in combo_stats.items()
        ],
        "probabilityEvaluation": all_probability,
        "recent30": recent_probability,
        "calibration": calibration,
        "calibrationError": calibration_error,
    }


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
    for item in matches:
        result = connection.execute(
            """SELECT full_time_score,half_time_score,actual_outcome,settled_at
               FROM match_results WHERE match_id=?""",
            (item["matchId"],),
        ).fetchone()
        if result:
            item["result"] = {
                "fullTimeScore": result[0], "halfTimeScore": result[1],
                "actualOutcome": result[2], "settledAt": result[3],
            }
        settlement = connection.execute(
            """SELECT outcome_hit,score_hit,total_goals_hit,over_under_hit
               FROM prediction_settlements WHERE match_id=?""",
            (item["matchId"],),
        ).fetchone()
        if settlement:
            item["settlement"] = {
                "outcomeHit": bool(settlement[0]) if settlement[0] is not None else None,
                "scoreHit": bool(settlement[1]) if settlement[1] is not None else None,
                "totalGoalsHit": bool(settlement[2]) if settlement[2] is not None else None,
                "overUnderHit": bool(settlement[3]) if settlement[3] is not None else None,
            }
    recommendations, recommendation_decisions = build_recommendations(matches, business_dates)
    save_combo_recommendations(connection, recommendations, collected_at)
    settle_combo_recommendations(connection, collected_at)
    performance = performance_summary(connection)
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
            "recommendationDecisions": recommendation_decisions,
            "performance": performance,
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
            result_count = settled_count = 0
            result_error = None
            history_saved = 0
            history_full_sync = False
            fundamental_stats = {"matched": 0, "enriched": 0, "lineups": 0}
            fundamental_error = None
            try:
                official_results, history_saved, history_full_sync = sync_official_history(
                    connection, args.timeout, args.retries
                )
                result_count, settled_count = settle_match_results(
                    connection, official_results, collected_at
                )
            except Exception as error:
                result_error = str(error)
                logging.warning("official history/result sync skipped: %s", error)
            try:
                fundamental_stats = enrich_fundamentals(
                    connection, args.api_football_key, matches, collected_at,
                    args.timeout, args.retries,
                )
            except Exception as error:
                fundamental_error = str(error)
                logging.warning("fundamental enrichment skipped: %s", error)
                with connection:
                    for match_id, payload_text in connection.execute(
                        "SELECT match_id,payload FROM current_matches"
                    ).fetchall():
                        item = json.loads(payload_text)
                        item["analysisSchedule"] = analysis_schedule(item)
                        locked = connection.execute(
                            "SELECT payload FROM locked_predictions WHERE match_id=?", (match_id,)
                        ).fetchone()
                        if locked:
                            frozen = json.loads(locked[0])
                            item["analysis"] = frozen.get("analysis", item["analysis"])
                            item["fundamentals"] = frozen.get("fundamentals")
                        else:
                            fundamentals = official_history_fundamentals(
                                connection, item, collected_at
                            )
                            fundamentals["message"] = (
                                "专业数据源暂不可用，已自动改用体彩官方历史样本"
                                if fundamentals["coverage"] else
                                "专业数据源暂不可用且历史样本不足，继续使用市场概率"
                            )
                            item["analysis"] = blend_fundamentals(item["analysis"], fundamentals)
                            item["fundamentals"] = fundamentals
                        connection.execute(
                            "UPDATE current_matches SET payload=? WHERE match_id=?",
                            (json.dumps(item, ensure_ascii=False, separators=(",", ":")), match_id),
                        )
            retained_count = export_current(
                connection, data_dir / "latest.json", collected_at, live_business_dates
            )
            website_push_error = None
            website_push_status = "disabled"
            if args.website_push_url:
                try:
                    push_latest_to_site(
                        data_dir / "latest.json", args.website_push_url,
                        args.website_push_auth_token, Path(args.relay_secret_file),
                        args.timeout, args.retries,
                    )
                    website_push_status = "ok"
                except Exception as error:
                    website_push_error = str(error)
                    website_push_status = "warning"
                    logging.warning("website push failed: %s", error)
            save_raw_snapshot(data_dir, raw, args.retention_days)
            health = {
                "status": "ok", "checkedAt": collected_at, "liveMatchCount": live_count,
                "retainedMatchCount": retained_count, "businessDates": live_business_dates,
                "officialCompletedCount": result_count, "settledPredictionCount": settled_count,
                "officialHistorySavedCount": history_saved,
                "officialHistoryFullSync": history_full_sync,
                "resultStatus": "ok" if result_error is None else "warning",
                "fundamentalStatus": (
                    ("warning" if result_error else "official_history") if not args.api_football_key else
                    "warning" if fundamental_error else "ok"
                ),
                "fundamentalMatchedCount": fundamental_stats["matched"],
                "fundamentalEnrichedCount": fundamental_stats["enriched"],
                "confirmedLineupCount": fundamental_stats["lineups"],
                "websitePushStatus": website_push_status,
                "source": "中国体育彩票官方接口",
            }
            if result_error:
                health["resultError"] = result_error
            if fundamental_error:
                health["fundamentalError"] = fundamental_error
            if website_push_error:
                health["websitePushError"] = website_push_error
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
    parser.add_argument("--api-football-key", default=os.environ.get("API_FOOTBALL_KEY", ""))
    parser.add_argument("--website-push-url", default=os.environ.get("FOOTBALL_AI_WEBSITE_PUSH_URL", ""))
    parser.add_argument("--website-push-auth-token", default=os.environ.get("FOOTBALL_AI_SITE_BYPASS_TOKEN", ""))
    parser.add_argument("--relay-secret-file", default=os.environ.get("FOOTBALL_AI_RELAY_SECRET_FILE", "/etc/football-ai/relay-secret"))
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

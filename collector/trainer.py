#!/usr/bin/env python3
"""Build a leakage-safe training dataset and train conservative calibration models."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


OUTCOMES = {"主胜": 0, "平局": 1, "客胜": 2}
MINIMUM_SAMPLES = 80
MINIMUM_VALIDATION = 20


def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS training_samples (
          match_id TEXT PRIMARY KEY,
          features TEXT NOT NULL,
          target_outcome INTEGER NOT NULL,
          home_goals INTEGER NOT NULL,
          away_goals INTEGER NOT NULL,
          locked_at TEXT NOT NULL,
          settled_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_training_samples_settled
          ON training_samples(settled_at);
        CREATE TABLE IF NOT EXISTS trained_models (
          version TEXT PRIMARY KEY,
          status TEXT NOT NULL,
          payload TEXT NOT NULL,
          trained_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_trained_models_status_time
          ON trained_models(status,trained_at);
        CREATE TABLE IF NOT EXISTS model_training_runs (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          started_at TEXT NOT NULL,
          finished_at TEXT,
          status TEXT NOT NULL,
          sample_count INTEGER NOT NULL DEFAULT 0,
          decision TEXT,
          payload TEXT,
          error TEXT
        );
        """
    )
    connection.execute("PRAGMA optimize")
    connection.commit()


def feature_row(payload: dict[str, Any]) -> dict[str, Any] | None:
    analysis = payload.get("analysis") or {}
    probabilities = analysis.get("probabilities") or {}
    try:
        values = [float(probabilities[key]) / 100 for key in ("home", "draw", "away")]
    except (KeyError, TypeError, ValueError):
        return None
    if not 0.99 <= sum(values) <= 1.01 or min(values) <= 0:
        return None
    expected = analysis.get("expectedGoals") or {}
    fundamentals = payload.get("fundamentals") or {}
    return {
        "probabilities": values,
        "expectedHomeGoals": float(expected.get("home") or 0),
        "expectedAwayGoals": float(expected.get("away") or 0),
        "fundamentalCoverage": int(fundamentals.get("coverage") or 0),
        "sourceModel": str(analysis.get("modelVersion") or "unknown"),
    }


def refresh_dataset(connection: sqlite3.Connection, updated_at: str) -> int:
    rows = connection.execute(
        """SELECT l.match_id,l.payload,l.locked_at,r.home_goals,r.away_goals,
                  r.actual_outcome,r.settled_at
           FROM locked_predictions l
           JOIN match_results r ON r.match_id=l.match_id
           ORDER BY r.settled_at,l.match_id"""
    ).fetchall()
    with connection:
        for match_id, payload_text, locked_at, home_goals, away_goals, outcome, settled_at in rows:
            try:
                features = feature_row(json.loads(payload_text))
            except (TypeError, ValueError):
                features = None
            if features is None or outcome not in OUTCOMES:
                continue
            connection.execute(
                """INSERT INTO training_samples
                   (match_id,features,target_outcome,home_goals,away_goals,locked_at,settled_at,updated_at)
                   VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(match_id) DO UPDATE SET
                   features=excluded.features,target_outcome=excluded.target_outcome,
                   home_goals=excluded.home_goals,away_goals=excluded.away_goals,
                   locked_at=excluded.locked_at,settled_at=excluded.settled_at,
                   updated_at=excluded.updated_at""",
                (
                    str(match_id), json.dumps(features, separators=(",", ":")), OUTCOMES[outcome],
                    int(home_goals), int(away_goals), str(locked_at), str(settled_at), updated_at,
                ),
            )
    return int(connection.execute("SELECT COUNT(*) FROM training_samples").fetchone()[0])


def calibrated(values: list[float], temperature: float) -> list[float]:
    powered = [max(1e-6, value) ** (1 / temperature) for value in values]
    total = sum(powered)
    return [value / total for value in powered]


def probability_metrics(rows: list[dict[str, Any]], temperature: float) -> dict[str, float]:
    brier = log_loss = hits = 0.0
    for row in rows:
        values = calibrated(row["features"]["probabilities"], temperature)
        target = row["target"]
        brier += sum((value - (1.0 if index == target else 0.0)) ** 2 for index, value in enumerate(values)) / 3
        log_loss += -math.log(max(1e-6, values[target]))
        hits += int(values.index(max(values)) == target)
    count = max(1, len(rows))
    return {
        "brierScore": round(brier / count, 5),
        "logLoss": round(log_loss / count, 5),
        "outcomeHitRate": round(hits / count * 100, 1),
    }


def goal_scales(rows: list[dict[str, Any]]) -> tuple[float, float]:
    home_expected = sum(row["features"]["expectedHomeGoals"] for row in rows)
    away_expected = sum(row["features"]["expectedAwayGoals"] for row in rows)
    home_actual = sum(row["homeGoals"] for row in rows)
    away_actual = sum(row["awayGoals"] for row in rows)
    prior = 25.0
    home = (home_actual + prior) / (home_expected + prior) if home_expected else 1.0
    away = (away_actual + prior) / (away_expected + prior) if away_expected else 1.0
    return max(0.8, min(1.2, home)), max(0.8, min(1.2, away))


def goal_mae(rows: list[dict[str, Any]], home_scale: float, away_scale: float) -> float:
    errors = []
    for row in rows:
        home = row["features"]["expectedHomeGoals"] * home_scale
        away = row["features"]["expectedAwayGoals"] * away_scale
        errors.append((abs(home - row["homeGoals"]) + abs(away - row["awayGoals"])) / 2)
    return round(sum(errors) / max(1, len(errors)), 4)


def load_samples(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = connection.execute(
        """SELECT match_id,features,target_outcome,home_goals,away_goals,settled_at
           FROM training_samples ORDER BY settled_at,match_id"""
    ).fetchall()
    return [
        {
            "matchId": row[0], "features": json.loads(row[1]), "target": int(row[2]),
            "homeGoals": int(row[3]), "awayGoals": int(row[4]), "settledAt": row[5],
        }
        for row in rows
    ]


def train(connection: sqlite3.Connection, trained_at: str) -> dict[str, Any]:
    samples = load_samples(connection)
    validation_count = max(MINIMUM_VALIDATION, int(len(samples) * 0.2)) if len(samples) >= MINIMUM_SAMPLES else 0
    training = samples[:-validation_count] if validation_count else samples
    validation = samples[-validation_count:] if validation_count else []
    best_temperature = 1.0
    best_loss = float("inf")
    for step in range(65, 166):
        temperature = step / 100
        loss = probability_metrics(training, temperature)["logLoss"]
        if loss < best_loss:
            best_loss, best_temperature = loss, temperature
    home_scale, away_scale = goal_scales(training)
    baseline = probability_metrics(validation, 1.0) if validation else probability_metrics(training, 1.0)
    candidate = probability_metrics(validation, best_temperature) if validation else probability_metrics(training, best_temperature)
    baseline["goalMae"] = goal_mae(validation or training, 1.0, 1.0)
    candidate["goalMae"] = goal_mae(validation or training, home_scale, away_scale)
    enough = len(samples) >= MINIMUM_SAMPLES and len(validation) >= MINIMUM_VALIDATION
    gates = {
        "enoughSamples": enough,
        "brierImproved": candidate["brierScore"] <= baseline["brierScore"] - 0.0005,
        "logLossStable": candidate["logLoss"] <= baseline["logLoss"],
        "goalErrorStable": candidate["goalMae"] <= baseline["goalMae"] + 0.03,
    }
    promote = all(gates.values())
    active_row = connection.execute(
        "SELECT version,payload FROM trained_models WHERE status='active' ORDER BY trained_at DESC LIMIT 1"
    ).fetchone()
    active_version = active_row[0] if active_row else None
    active_metrics = None
    rollback = False
    if active_row and validation and not promote:
        active_payload = json.loads(active_row[1])
        active_parameters = active_payload.get("parameters") or {}
        active_metrics = probability_metrics(
            validation, float(active_parameters.get("temperature") or 1.0)
        )
        active_metrics["goalMae"] = goal_mae(
            validation,
            float(active_parameters.get("homeGoalScale") or 1.0),
            float(active_parameters.get("awayGoalScale") or 1.0),
        )
        rollback = (
            active_metrics["brierScore"] > baseline["brierScore"] + 0.01
            or active_metrics["logLoss"] > baseline["logLoss"] + 0.03
            or active_metrics["goalMae"] > baseline["goalMae"] + 0.10
        )
        if rollback:
            active_version = None
    fingerprint = hashlib.sha256(
        "|".join(row["matchId"] for row in samples).encode()
    ).hexdigest()[:10]
    version = f"v4-trained-{trained_at[:10].replace('-', '')}-{fingerprint}"
    local_now = datetime.fromisoformat(trained_at).astimezone(ZoneInfo("Asia/Shanghai"))
    next_run = local_now.replace(hour=4, minute=10, second=0, microsecond=0)
    if next_run <= local_now:
        next_run += timedelta(days=1)
    decision = "promote" if promote else "rollback" if rollback else "hold" if enough else "collecting"
    result = {
        "status": "ok" if enough else "collecting",
        "decision": decision,
        "message": (
            "候选模型通过独立验证集，已自动启用。" if promote else
            "现行训练模型在最新验证集明显退化，已自动回退基础模型。" if rollback else
            "候选模型未通过全部安全门槛，继续使用现行模型。" if enough else
            f"训练样本仍在积累，至少需要{MINIMUM_SAMPLES}场。"
        ),
        "trainedAt": trained_at,
        "nextRunAt": next_run.isoformat(),
        "sampleCount": len(samples),
        "trainingCount": len(training),
        "validationCount": len(validation),
        "candidateVersion": version,
        "activeVersion": version if promote else active_version,
        "parameters": {
            "temperature": best_temperature,
            "homeGoalScale": round(home_scale, 4),
            "awayGoalScale": round(away_scale, 4),
        },
        "baseline": baseline,
        "candidate": candidate,
        "activeMetrics": active_metrics,
        "gates": gates,
    }
    payload = json.dumps(result, ensure_ascii=False, separators=(",", ":"))
    with connection:
        if promote or rollback:
            connection.execute("UPDATE trained_models SET status='retired' WHERE status='active'")
        connection.execute(
            "INSERT OR REPLACE INTO trained_models(version,status,payload,trained_at) VALUES (?,?,?,?)",
            (version, "active" if promote else "candidate", payload, trained_at),
        )
    return result


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", default="/var/lib/football-ai/football-ai.sqlite3")
    parser.add_argument("--status-file", default="/var/lib/football-ai/training-status.json")
    args = parser.parse_args()
    started_at = utc_iso()
    connection = sqlite3.connect(args.database, timeout=30)
    schema(connection)
    run_id = connection.execute(
        "INSERT INTO model_training_runs(started_at,status) VALUES (?,'running')", (started_at,)
    ).lastrowid
    connection.commit()
    try:
        sample_count = refresh_dataset(connection, started_at)
        result = train(connection, started_at)
        result["sampleCount"] = sample_count
        atomic_json(Path(args.status_file), result)
        with connection:
            connection.execute(
                """UPDATE model_training_runs SET finished_at=?,status='ok',sample_count=?,
                   decision=?,payload=? WHERE id=?""",
                (utc_iso(), sample_count, result["decision"], json.dumps(result, ensure_ascii=False), run_id),
            )
        return 0
    except Exception as error:
        with connection:
            connection.execute(
                "UPDATE model_training_runs SET finished_at=?,status='error',error=? WHERE id=?",
                (utc_iso(), str(error), run_id),
            )
        raise
    finally:
        connection.close()


if __name__ == "__main__":
    raise SystemExit(main())

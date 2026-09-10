#!/usr/bin/env python3
"""Create a consistent compressed daily backup of the collector database."""

from __future__ import annotations

import gzip
import os
import shutil
import sqlite3
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path


DATA_DIR = Path(os.environ.get("FOOTBALL_AI_DATA_DIR", "/var/lib/football-ai"))
DATABASE = Path(os.environ.get("FOOTBALL_AI_DATABASE", str(DATA_DIR / "football-ai.sqlite3")))


def main() -> None:
    backup_dir = DATA_DIR / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.now(timezone(timedelta(hours=8))).date().isoformat()
    destination = backup_dir / f"football-ai-{today}.sqlite3.gz"
    handle, temporary_name = tempfile.mkstemp(prefix="football-ai-backup-", suffix=".sqlite3")
    os.close(handle)
    temporary = Path(temporary_name)
    compressed = destination.with_suffix(destination.suffix + ".tmp")
    try:
        with sqlite3.connect(DATABASE) as source, sqlite3.connect(temporary) as target:
            source.backup(target)
        with temporary.open("rb") as source, gzip.open(compressed, "wb", compresslevel=6) as target:
            shutil.copyfileobj(source, target)
        os.replace(compressed, destination)
    finally:
        temporary.unlink(missing_ok=True)
        compressed.unlink(missing_ok=True)
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    for path in backup_dir.glob("football-ai-*.sqlite3.gz"):
        if datetime.fromtimestamp(path.stat().st_mtime, timezone.utc) < cutoff:
            path.unlink()


if __name__ == "__main__":
    main()

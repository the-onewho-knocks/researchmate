import json
import logging
import time
from pathlib import Path


def setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def log_usage(data_dir: Path, record: dict) -> None:
    """Append one JSON line per evaluation (feeds scripts/cost_report.py)."""
    data_dir.mkdir(parents=True, exist_ok=True)
    row = {"ts": time.time(), **record}
    with open(data_dir / "usage.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")
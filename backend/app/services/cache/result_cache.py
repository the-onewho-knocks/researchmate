"""backend/app/services/cache/result_cache.py"""
import hashlib
import json
import re
import time
from pathlib import Path

_ID = re.compile(r"^[0-9a-f]{32}$")


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


class ResultCache:
    """File-based cache. The key covers everything that changes the result."""

    def __init__(self, base: Path, ttl_hours: int = 24):
        self.dir = Path(base) / "cache"
        self.ttl_seconds = ttl_hours * 3600
        self.dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def make_key(
        file_hash: str, framework_version: str, prompt_version: str,
        model: str, coach: bool, ml: bool, suggest: bool = False,
    ) -> str:
        raw = "|".join(
            [file_hash, framework_version, prompt_version, model, str(coach), str(ml), str(suggest)]
        )
        return hashlib.sha256(raw.encode()).hexdigest()

    def _path(self, name: str) -> Path:
        return self.dir / f"{name}.json"

    def get(self, key: str) -> dict | None:
        p = self._path(key)
        if not p.exists() or time.time() - p.stat().st_mtime > self.ttl_seconds:
            return None
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    def set(self, key: str, report: dict) -> None:
        self._path(key).write_text(json.dumps(report), encoding="utf-8")

    def save_report(self, document_id: str, report: dict) -> None:
        if _ID.match(document_id):
            self._path(f"report_{document_id}").write_text(json.dumps(report), encoding="utf-8")

    def load_report(self, document_id: str) -> dict | None:
        if not _ID.match(document_id):
            return None
        return self.get(f"report_{document_id}")

    def cleanup(self) -> int:
        now = time.time()
        removed = 0
        for p in self.dir.glob("*.json"):
            if now - p.stat().st_mtime > self.ttl_seconds:
                p.unlink(missing_ok=True)
                removed += 1
        return removed

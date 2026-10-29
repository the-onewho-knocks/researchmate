"""backend/app/services/llm/rate_limit.py"""
"""Local guard around the Gemini quota.

Gemini's free tier limits requests per minute, tokens per minute and requests per
day. Without a guard one evaluation can trip the per-minute limit, and the whole
request then fails. Here we track all three, persist the daily counter so a
restart does not reset it, and expose a circuit breaker for real 429s.
"""
import json
import threading
import time
from collections import deque
from datetime import date
from pathlib import Path


class GeminiQuota:
    def __init__(
        self,
        data_dir: Path | None = None,
        rpm: int = 10,
        tpm: int = 250_000,
        rpd: int = 250,
    ):
        self.rpm = max(1, rpm)
        self.tpm = max(1, tpm)
        self.rpd = max(1, rpd)
        self._path = Path(data_dir) / "gemini_quota.json" if data_dir else None

        self._lock = threading.Lock()
        self._minute: deque[float] = deque()
        self._minute_tokens: deque[tuple[float, int]] = deque()
        self._cooldown_until = 0.0

        self._day = date.today().isoformat()
        self._day_calls = 0
        self._day_tokens = 0
        self._load()

    # ---- persistence -------------------------------------------------

    def _load(self) -> None:
        if not self._path or not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        if data.get("date") == self._day:
            self._day_calls = int(data.get("calls", 0) or 0)
            self._day_tokens = int(data.get("tokens", 0) or 0)

    def _save(self) -> None:
        if not self._path:
            return
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(
                json.dumps(
                    {"date": self._day, "calls": self._day_calls, "tokens": self._day_tokens}
                ),
                encoding="utf-8",
            )
        except OSError:
            pass

    def _roll_day(self) -> None:
        today = date.today().isoformat()
        if today != self._day:
            self._day = today
            self._day_calls = 0
            self._day_tokens = 0

    # ---- queries -----------------------------------------------------

    def cooling_down(self) -> bool:
        with self._lock:
            return time.time() < self._cooldown_until

    def cooldown_remaining(self) -> float:
        with self._lock:
            return max(0.0, self._cooldown_until - time.time())

    def remaining_calls(self) -> int:
        with self._lock:
            self._roll_day()
            return max(0, self.rpd - self._day_calls)

    def can_call(self, estimated_input: int = 0) -> bool:
        now = time.time()
        with self._lock:
            self._roll_day()
            if now < self._cooldown_until:
                return False
            if self._day_calls >= self.rpd:
                return False
            while self._minute and now - self._minute[0] > 60:
                self._minute.popleft()
            if len(self._minute) >= self.rpm:
                return False
            while self._minute_tokens and now - self._minute_tokens[0][0] > 60:
                self._minute_tokens.popleft()
            used = sum(t for _, t in self._minute_tokens)
            return used + estimated_input <= self.tpm

    # ---- updates -----------------------------------------------------

    def record(self, input_tokens: int, output_tokens: int) -> None:
        now = time.time()
        with self._lock:
            self._roll_day()
            self._minute.append(now)
            self._minute_tokens.append((now, max(0, input_tokens) + max(0, output_tokens)))
            self._day_calls += 1
            self._day_tokens += max(0, input_tokens) + max(0, output_tokens)
            self._save()

    def trip(self, seconds: float = 60.0) -> None:
        """A real 429 arrived: stop sending to this provider for a while."""
        with self._lock:
            self._cooldown_until = max(self._cooldown_until, time.time() + seconds)

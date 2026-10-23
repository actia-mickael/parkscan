"""Limitation de débit en mémoire (seau à jetons par clé). Suffisant pour un backend mono-instance."""

import time


class TokenBucketLimiter:
    def __init__(
        self, rate_per_minute: int, burst: int | None = None, max_keys: int = 10_000
    ) -> None:
        self.rate = rate_per_minute / 60.0
        self.capacity = float(burst or rate_per_minute)
        self.max_keys = max_keys
        self._buckets: dict[str, tuple[float, float]] = {}  # clé -> (jetons, dernier passage)

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        tokens, last = self._buckets.get(key, (self.capacity, now))
        tokens = min(self.capacity, tokens + (now - last) * self.rate)
        if len(self._buckets) >= self.max_keys and key not in self._buckets:
            self._prune(now)
        if tokens < 1.0:
            self._buckets[key] = (tokens, now)
            return False
        self._buckets[key] = (tokens - 1.0, now)
        return True

    def _prune(self, now: float) -> None:
        # Supprime les clés inactives depuis plus d'une minute (leur seau est de toute façon plein).
        stale = [k for k, (_, last) in self._buckets.items() if now - last > 60]
        for k in stale:
            del self._buckets[k]

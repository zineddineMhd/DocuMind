"""Limiteur de débit en mémoire (fenêtre glissante). Suffisant pour une instance ; Redis en évolution."""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from app.core.errors import AppError

_hits: dict[str, deque[float]] = defaultdict(deque)
_lock = threading.Lock()


def check(key: str, limit: int, window_s: float = 60.0) -> None:
    if limit <= 0:
        return
    now = time.monotonic()
    with _lock:
        q = _hits[key]
        while q and now - q[0] > window_s:
            q.popleft()
        if len(q) >= limit:
            raise AppError(429, "Trop de requêtes. Réessayez dans une minute.")
        q.append(now)


def reset() -> None:
    with _lock:
        _hits.clear()

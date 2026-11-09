"""Small single-process safeguards; public deployments need a shared gateway."""
from collections import deque
from threading import Lock
from time import monotonic

from fastapi import HTTPException, Request
from groq import APITimeoutError, RateLimitError

_hits: dict[str, deque[float]] = {}
_lock = Lock()


def limit_ai_requests(request: Request) -> None:
    now = monotonic()
    client = request.client.host if request.client else 'unknown'
    with _lock:
        for key in list(_hits):
            while _hits[key] and _hits[key][0] <= now - 60:
                _hits[key].popleft()
            if not _hits[key]:
                del _hits[key]
        hits = _hits.setdefault(client, deque())
        if len(hits) >= 30:
            raise HTTPException(status_code=429, detail='Too many requests. Please try again later.', headers={'Retry-After': '60'})
        hits.append(now)


def require_decision_authorization() -> None:
    # Fail closed until an authentication and authorization design is approved.
    raise HTTPException(status_code=403, detail='Investigation decisions are disabled pending authorization setup.')


def provider_status(exc: Exception) -> int:
    if isinstance(exc, RateLimitError):
        return 429
    if isinstance(exc, (APITimeoutError, TimeoutError)):
        return 504
    return 503

"""Small single-process safeguards; public deployments need a shared gateway."""
from collections import deque
from secrets import compare_digest
from threading import Lock
from time import monotonic

from fastapi import Header, HTTPException, Request
from groq import APITimeoutError, RateLimitError
from backend.app.config import get_settings

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


def require_decision_authorization(authorization: str | None = Header(default=None)) -> None:
    configured = get_settings().admin_token
    expected = configured.get_secret_value() if configured else ''
    scheme, _, supplied = (authorization or '').partition(' ')
    if not expected or scheme.lower() != 'bearer' or not supplied or not compare_digest(supplied.encode('utf-8'), expected.encode('utf-8')):
        raise HTTPException(status_code=401, detail='Unauthorized.', headers={'WWW-Authenticate': 'Bearer'})


def provider_status(exc: Exception) -> int:
    if isinstance(exc, RateLimitError):
        return 429
    if isinstance(exc, (APITimeoutError, TimeoutError)):
        return 504
    return 503

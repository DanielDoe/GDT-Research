"""Small HTTP client with throttling and retries.

Public providers are called directly. Tests pass a recorded response through
the provider `fetcher` argument instead of this client.
"""

from __future__ import annotations

import time
import urllib.error
import urllib.request
from typing import Callable
from urllib.parse import urlparse

from gdt_agents.errors import ProviderError
from gdt_agents.settings import USER_AGENT

Fetcher = Callable[[str, dict[str, str]], tuple[int, bytes]]

_last_request: dict[str, float] = {}
_MIN_INTERVAL_S = 0.25


def _throttle(url: str) -> None:
    host = urlparse(url).netloc
    now = time.monotonic()
    wait = _last_request.get(host, 0.0) + _MIN_INTERVAL_S - now
    if wait > 0:
        time.sleep(wait)
    _last_request[host] = time.monotonic()


def fetch_bytes(url: str, headers: dict[str, str] | None = None, *, provider: str) -> bytes:
    merged = {"User-Agent": USER_AGENT, "Accept": "*/*"}
    if headers:
        merged.update(headers)
    delay = 1.0
    last_error: Exception | None = None
    for attempt in range(3):
        _throttle(url)
        request = urllib.request.Request(url, headers=merged)
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")[:500]
            retryable = exc.code in {429, 500, 502, 503, 504}
            retry_after = exc.headers.get("Retry-After") if exc.headers else None
            last_error = ProviderError(
                f"{provider} returned HTTP {exc.code}. {body}".strip(),
                provider=provider,
                retryable=retryable,
                status_code=503 if retryable else 502,
            )
            if not retryable or attempt == 2:
                raise last_error
            try:
                delay = float(retry_after) if retry_after else delay
            except ValueError:
                pass
            time.sleep(min(delay, 30))
            delay *= 2
        except urllib.error.URLError as exc:
            last_error = ProviderError(
                f"{provider} could not be reached: {exc.reason}",
                provider=provider,
                retryable=True,
            )
            if attempt == 2:
                raise last_error
            time.sleep(delay)
            delay *= 2
    raise ProviderError(f"{provider} request failed.", provider=provider, retryable=True)

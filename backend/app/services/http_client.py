"""One shared HTTP client so AI and provider calls reuse open connections."""

from __future__ import annotations

import threading

import httpx

_lock = threading.Lock()
_client: httpx.Client | None = None


def shared_client() -> httpx.Client:
    global _client
    with _lock:
        if _client is None or _client.is_closed:
            _client = httpx.Client(
                limits=httpx.Limits(max_connections=100, max_keepalive_connections=40),
                follow_redirects=False,
            )
        return _client

"""Quip API client with automatic retry and exponential backoff."""

from __future__ import annotations

import logging
import os
import random
import time
from typing import Any

import httpx

QUIP_API_BASE = "https://platform.quip.com/1"

log = logging.getLogger(__name__)

_MAX_RETRIES = 5
_BASE_DELAY = 1.0
_RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})


class QuipAuthError(Exception):
    pass


class QuipAPIError(Exception):
    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        super().__init__(f"HTTP {status_code}: {message}")


def _backoff(attempt: int, retry_after: str | None = None) -> float:
    """Return the delay in seconds for *attempt* (0-indexed)."""
    if retry_after is not None:
        try:
            return float(retry_after)
        except ValueError:
            pass
    delay = _BASE_DELAY * (2 ** attempt)
    delay += delay * 0.1 * random.uniform(-1.0, 1.0)
    return delay


class QuipClient:
    def __init__(self, token: str | None = None) -> None:
        resolved = token or os.environ.get("QUIP_TOKEN")
        if not resolved:
            raise QuipAuthError(
                "No Quip token provided. Set QUIP_TOKEN env var or pass --token."
            )
        self._http = httpx.Client(
            base_url=QUIP_API_BASE,
            headers={"Authorization": f"Bearer {resolved}"},
            timeout=30,
        )

    def _get(self, path: str, **params: Any) -> Any:
        for attempt in range(_MAX_RETRIES + 1):
            try:
                response = self._http.get(path, params=params)
            except httpx.TimeoutException as exc:
                if attempt == _MAX_RETRIES:
                    raise QuipAPIError(-1, f"Network timeout after {_MAX_RETRIES} retries") from exc
                delay = _backoff(attempt)
                log.warning(
                    "Timeout on attempt %d/%d for %s; retrying in %.1fs",
                    attempt + 1, _MAX_RETRIES, path, delay,
                )
                time.sleep(delay)
                continue

            if response.status_code == 200:
                return response.json()

            if response.status_code not in _RETRYABLE_STATUS or attempt == _MAX_RETRIES:
                raise QuipAPIError(response.status_code, response.text)

            retry_after = response.headers.get("Retry-After")
            delay = _backoff(attempt, retry_after)
            log.warning(
                "HTTP %d on attempt %d/%d for %s; retrying in %.1fs",
                response.status_code, attempt + 1, _MAX_RETRIES, path, delay,
            )
            time.sleep(delay)

        # Unreachable but satisfies type checker
        raise QuipAPIError(-1, "Retry exhausted")  # pragma: no cover

    def get_thread(self, thread_id: str) -> dict[str, Any]:
        return self._get(f"/threads/{thread_id}")  # type: ignore[return-value]

    def get_folder(self, folder_id: str) -> dict[str, Any]:
        return self._get(f"/folders/{folder_id}")  # type: ignore[return-value]

    def get_current_user(self) -> dict[str, Any]:
        return self._get("/users/current")  # type: ignore[return-value]

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> QuipClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

"""Quip API client."""

from __future__ import annotations

import os
from typing import Any

import httpx

QUIP_API_BASE = "https://platform.quip.com/1"


class QuipAuthError(Exception):
    pass


class QuipAPIError(Exception):
    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        super().__init__(f"HTTP {status_code}: {message}")


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
        response = self._http.get(path, params=params)
        if response.status_code != 200:
            raise QuipAPIError(response.status_code, response.text)
        return response.json()

    def get_thread(self, thread_id: str) -> dict[str, Any]:
        return self._get(f"/threads/{thread_id}")  # type: ignore[return-value]

    def get_folder(self, folder_id: str) -> dict[str, Any]:
        return self._get(f"/folders/{folder_id}")  # type: ignore[return-value]

    def get_current_user(self) -> dict[str, Any]:
        return self._get("/users/current")  # type: ignore[return-value]

    def get_blob(self, thread_id: str, blob_name: str) -> bytes:
        response = self._http.get(f"/blob/{thread_id}/{blob_name}")
        if response.status_code != 200:
            raise QuipAPIError(response.status_code, response.text)
        return response.content

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> QuipClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

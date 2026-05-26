"""Token resolution and validation for quip-export."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import httpx

CONFIG_PATH = Path.home() / ".config" / "quip-export" / "config.toml"


class QuipAuthError(Exception):
    pass


def resolve_token(flag_token: str | None = None) -> str:
    """Return the best available token from flag > env > config file."""
    if flag_token:
        return flag_token

    env = os.environ.get("QUIP_TOKEN", "")
    if env:
        return env

    if CONFIG_PATH.exists():
        try:
            try:
                import tomllib  # type: ignore[import-not-found]
            except ImportError:
                import tomli as tomllib  # type: ignore[import-not-found,no-redef]

            with open(CONFIG_PATH, "rb") as fh:
                data = tomllib.load(fh)
        except Exception as exc:
            raise type(exc)(f"{CONFIG_PATH}: {exc}") from exc

        token = data.get("token", "")
        if token:
            return token

    raise QuipAuthError(
        "No QUIP_TOKEN found. Set it via --token flag, QUIP_TOKEN env var, "
        f"or {CONFIG_PATH}."
    )


def validate_token(token: str) -> dict[str, Any]:
    """Call the Quip API to verify the token and return the current user dict."""
    try:
        resp = httpx.get(
            "https://platform.quip.com/1/users/current",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
    except httpx.TimeoutException as exc:
        raise TimeoutError("Network timeout connecting to Quip API") from exc

    if resp.status_code in (401, 403):
        raise QuipAuthError(f"Invalid token (HTTP {resp.status_code})")
    resp.raise_for_status()
    return resp.json()["current_user"]

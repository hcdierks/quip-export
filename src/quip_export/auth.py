"""Token resolution for quip-export."""

from __future__ import annotations

import os
from pathlib import Path
from typing import cast

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
                import tomllib
            except ImportError:
                import tomli as tomllib  # type: ignore[no-redef]

            with open(CONFIG_PATH, "rb") as fh:
                data = tomllib.load(fh)
        except Exception as exc:
            raise type(exc)(f"{CONFIG_PATH}: {exc}") from exc

        token = data.get("token", "")
        if token:
            return cast(str, token)

    raise QuipAuthError(
        "No QUIP_TOKEN found. Set it via --token flag, QUIP_TOKEN env var, "
        f"or {CONFIG_PATH}."
    )

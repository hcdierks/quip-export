"""Structured log file written to {output_dir}/run.log during a sync run."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import IO


def _ts() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class RunLogger:
    """Appends structured entries to <output_dir>/run.log.

    Format: [ISO8601_TIMESTAMP] [LEVEL] [CONTEXT] MESSAGE

    Writes are flushed immediately so a crash preserves all prior entries.
    Opening the log file is non-fatal — if the directory is read-only,
    WARNING/ERROR still appear on stderr and the run continues.
    """

    def __init__(
        self,
        output_dir: Path,
        verbose: bool = False,
        token: str | None = None,
    ) -> None:
        self._verbose = verbose
        self._token = token or ""
        self._fh: IO[str] | None = None

        try:
            self._fh = open(output_dir / "run.log", "a", encoding="utf-8")  # noqa: SIM115
        except OSError as exc:
            print(
                f"WARNING: cannot open run.log in {output_dir}: {exc}",
                file=sys.stderr,
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def info(self, context: str, message: str) -> None:
        self._write("INFO", context, message)

    def warning(self, context: str, message: str) -> None:
        self._write("WARNING", context, message)

    def error(self, context: str, message: str) -> None:
        self._write("ERROR", context, message)

    def close(self) -> None:
        if self._fh is not None:
            self._fh.close()
            self._fh = None

    def __enter__(self) -> RunLogger:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _write(self, level: str, context: str, message: str) -> None:
        clean = self._scrub(message)
        line = f"[{_ts()}] [{level}] [{context}] {clean}"

        if self._fh is not None:
            self._fh.write(line + "\n")
            self._fh.flush()

        if level in ("WARNING", "ERROR"):
            print(line, file=sys.stderr)
        elif level == "INFO" and self._verbose:
            print(line)

    def _scrub(self, text: str) -> str:
        if self._token and self._token in text:
            return text.replace(self._token, "***")
        return text

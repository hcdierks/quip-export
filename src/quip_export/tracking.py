"""Real-time progress state files and post-run reports written to the output directory."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from quip_export.models import ClassifiedThread, DuplicateRecord, FolderTree


def _now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _now_z() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


_MD_SPECIAL = re.compile(r'([*_#`|\\])')


def _escape_md(text: str) -> str:
    return _MD_SPECIAL.sub(r'\\\1', text)


def _atomic_write(dest: Path, content: str) -> None:
    tmp = dest.with_suffix(".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(dest)


# ---------------------------------------------------------------------------
# StateTracker
# ---------------------------------------------------------------------------

class StateTracker:
    """Writes Markdown progress files into *output_dir* as the export runs.

    All writes are atomic (write to .tmp then rename) and non-fatal — errors
    during state tracking never abort an export.
    """

    def __init__(self, output_dir: Path) -> None:
        self._dir = output_dir
        self._safe_write(
            self._dir / "run_state.md",
            f"# Export State\n\nstart: {_now()}\nstage: started\n",
        )

    def update_stage(self, stage: str) -> None:
        self._safe_write(
            self._dir / "run_state.md",
            f"# Export State\n\nstart: {_now()}\nstage: {stage}\n",
        )

    def record_folders(self, tree: FolderTree) -> None:
        lines = ["# Discovered Folders\n"]
        for folder_id, node in tree.index.items():
            lines.append(f"- {folder_id}: {node.title}")
        self._safe_write(self._dir / "folders.md", "\n".join(lines) + "\n")

    def record_thread(self, thread: ClassifiedThread) -> None:
        objects_path = self._dir / "objects.md"
        try:
            existing = objects_path.read_text() if objects_path.exists() else "# Objects\n\n"
        except OSError:
            existing = "# Objects\n\n"
        line = f"- {thread.thread_id}: {thread.title} ({thread.thread_class})\n"
        self._safe_write(objects_path, existing + line)

    def record_export(self, thread_id: str, path: Path, status: str) -> None:
        exports_path = self._dir / "exports.md"
        try:
            existing = exports_path.read_text() if exports_path.exists() else "# Exports\n\n"
        except OSError:
            existing = "# Exports\n\n"
        line = f"- {thread_id}: {path} [{status}]\n"
        self._safe_write(exports_path, existing + line)

    def _safe_write(self, dest: Path, content: str) -> None:
        try:
            _atomic_write(dest, content)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Duplicates report
# ---------------------------------------------------------------------------

def write_duplicates_report(
    records: list[DuplicateRecord],
    base_dir: Path,
    logger: Any | None = None,
) -> None:
    """Write duplicates.md to *base_dir* listing all multi-location exports.

    Records with no successful paths are omitted with a warning.
    The write is atomic (.tmp + rename) and non-fatal on IO error.
    """
    valid: list[DuplicateRecord] = []
    for rec in records:
        if not rec.paths:
            msg = f"DuplicateRecord for '{rec.thread_id}' has no paths — omitted"
            if logger is not None:
                logger.warning("duplicates", msg)
        else:
            valid.append(rec)

    ts = _now_z()
    lines = [
        "# Duplicate Exports",
        f"Generated: {ts}",
        f"Total documents duplicated: {len(valid)}",
    ]

    if not valid:
        lines += ["", "No duplicates found."]
    else:
        for rec in valid:
            lines.append("")
            lines.append(f"## {_escape_md(rec.title)} _(thread: `{rec.thread_id}`)_")
            for path in rec.paths:
                try:
                    rel = path.relative_to(base_dir)
                    path_str = f"./{rel}"
                except ValueError:
                    path_str = str(path)
                lines.append(f"- `{path_str}`")

    content = "\n".join(lines) + "\n"
    dest = base_dir / "duplicates.md"
    try:
        _atomic_write(dest, content)
    except OSError as exc:
        if logger is not None:
            logger.error("duplicates", f"Failed to write duplicates.md: {exc}")

"""Real-time progress state files written alongside the export output."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path


def _now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()

from quip_export.models import ClassifiedThread, FolderTree


class StateTracker:
    """Writes Markdown progress files into *output_dir* as the export runs.

    All writes are atomic (write to .tmp then rename) and non-fatal — errors
    during state tracking never abort an export.
    """

    def __init__(self, output_dir: Path) -> None:
        self._dir = output_dir
        self._atomic_write(
            self._dir / "run_state.md",
            f"# Export State\n\nstart: {_now()}\nstage: started\n",
        )

    def update_stage(self, stage: str) -> None:
        self._atomic_write(
            self._dir / "run_state.md",
            f"# Export State\n\nstart: {_now()}\nstage: {stage}\n",
        )

    def record_folders(self, tree: FolderTree) -> None:
        lines = ["# Discovered Folders\n"]
        for folder_id, node in tree.index.items():
            lines.append(f"- {folder_id}: {node.title}")
        self._atomic_write(self._dir / "folders.md", "\n".join(lines) + "\n")

    def record_thread(self, thread: ClassifiedThread) -> None:
        objects_path = self._dir / "objects.md"
        try:
            existing = objects_path.read_text() if objects_path.exists() else "# Objects\n\n"
        except OSError:
            existing = "# Objects\n\n"
        line = f"- {thread.thread_id}: {thread.title} ({thread.thread_class})\n"
        self._atomic_write(objects_path, existing + line)

    def record_export(self, thread_id: str, path: Path, status: str) -> None:
        exports_path = self._dir / "exports.md"
        try:
            existing = exports_path.read_text() if exports_path.exists() else "# Exports\n\n"
        except OSError:
            existing = "# Exports\n\n"
        line = f"- {thread_id}: {path} [{status}]\n"
        self._atomic_write(exports_path, existing + line)

    def _atomic_write(self, dest: Path, content: str) -> None:
        tmp = dest.with_suffix(".tmp")
        try:
            tmp.write_text(content, encoding="utf-8")
            tmp.replace(dest)
        except OSError:
            pass

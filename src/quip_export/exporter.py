"""Orchestrates fetching a Quip thread and writing it in the requested formats."""

from __future__ import annotations

import logging
from enum import Enum
from pathlib import Path

from quip_export.client import QuipClient
from quip_export.formats import export_docx, export_markdown, export_pdf, export_pptx, export_xlsx
from quip_export.formats import get_format
from quip_export.models import ClassifiedThread, DuplicateRecord

log = logging.getLogger(__name__)


class OutputFormat(str, Enum):
    markdown = "md"
    docx = "docx"
    pdf = "pdf"


def export_thread(
    client: QuipClient,
    thread_id: str,
    output_dir: Path,
    formats: list[OutputFormat],
) -> list[Path]:
    thread = client.get_thread(thread_id)
    html: str = thread["html"]
    title: str = thread["thread"]["title"] or thread_id
    safe_title = "".join(c if c.isalnum() or c in " -_" else "_" for c in title).strip()

    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    for fmt in formats:
        path = output_dir / f"{safe_title}.{fmt.value}"
        if fmt == OutputFormat.markdown:
            export_markdown(html, path)
        elif fmt == OutputFormat.docx:
            export_docx(html, path)
        elif fmt == OutputFormat.pdf:
            export_pdf(html, path)
        written.append(path)

    return written


# Thread classes that go straight to Markdown without attempting a primary format
_MD_ONLY_CLASSES = {"chat", "code", "unknown"}


def export_with_fallback(html: str, output_path: Path, thread_class: str) -> Path:
    """Export HTML to the appropriate format, falling back to Markdown on error.

    Returns the path of the file that was actually written (may differ in suffix
    from *output_path* when the primary exporter fails).

    Each exporter is called by name so that tests can patch
    ``quip_export.exporter.export_<fmt>`` without bypassing this function.
    """
    if thread_class in _MD_ONLY_CLASSES:
        md_path = output_path.with_suffix(".md")
        export_markdown(html, md_path)
        return md_path

    try:
        if thread_class == "document":
            primary_path = output_path.with_suffix(".docx")
            export_docx(html, primary_path)
            return primary_path
        if thread_class == "spreadsheet":
            primary_path = output_path.with_suffix(".xlsx")
            export_xlsx(html, primary_path)
            return primary_path
        if thread_class == "slides":
            primary_path = output_path.with_suffix(".pptx")
            export_pptx(html, primary_path)
            return primary_path
    except Exception as exc:
        log.warning(
            "Primary export failed for %s (%s): %s — falling back to Markdown",
            output_path.stem,
            thread_class,
            exc,
        )

    md_path = output_path.with_suffix(".md")
    export_markdown(html, md_path)
    return md_path


def export_classified_thread(
    thread: ClassifiedThread,
    html: str,
    folder_path_map: dict[str, Path],
) -> DuplicateRecord | None:
    """Write a thread to each of its folders, returning a DuplicateRecord when there are multiple copies.

    Skips folders not present in *folder_path_map* (logs a warning).
    Partial failures are tolerated; only successfully written paths are tracked.
    Returns None if zero or one copy was written.
    """
    fmt = get_format(thread.thread_class)
    safe_name = "".join(
        c if c.isalnum() or c in " -_." else "_" for c in thread.title
    ).strip() or thread.thread_id

    written: list[Path] = []
    for folder_id in thread.folder_ids:
        folder_path = folder_path_map.get(folder_id)
        if folder_path is None:
            log.warning(
                "Thread %s references unknown folder %s — skipping",
                thread.thread_id,
                folder_id,
            )
            continue

        dest = folder_path / (safe_name + fmt.extension)
        try:
            result = export_with_fallback(html, dest, thread.thread_class)
            written.append(result)
        except Exception as exc:
            log.error(
                "Failed to export thread %s to %s: %s",
                thread.thread_id,
                dest,
                exc,
            )

    if len(written) > 1:
        return DuplicateRecord(
            thread_id=thread.thread_id,
            title=thread.title,
            paths=written,
        )
    return None

"""Orchestrates fetching a Quip thread and writing it in the requested formats."""

from __future__ import annotations

from enum import Enum
from pathlib import Path

from quip_export.client import QuipClient
from quip_export.formats import export_docx, export_markdown, export_pdf


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

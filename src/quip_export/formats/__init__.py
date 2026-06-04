"""Output format exporters and format-to-exporter mapping."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from quip_export.formats.docx import export_docx
from quip_export.formats.markdown import export_markdown
from quip_export.formats.pdf import export_pdf
from quip_export.formats.pptx import export_pptx
from quip_export.formats.xlsx import export_xlsx


@dataclass(frozen=True)
class FormatSpec:
    extension: str
    exporter: Callable


FORMAT_MAP: dict[str, FormatSpec] = {
    "document": FormatSpec(extension=".docx", exporter=export_docx),
    "spreadsheet": FormatSpec(extension=".xlsx", exporter=export_xlsx),
    "slides": FormatSpec(extension=".pptx", exporter=export_pptx),
    "chat": FormatSpec(extension=".md", exporter=export_markdown),
    "code": FormatSpec(extension=".md", exporter=export_markdown),
    "unknown": FormatSpec(extension=".md", exporter=export_markdown),
}

_MD_FORMAT = FormatSpec(extension=".md", exporter=export_markdown)


def get_format(thread_class: str) -> FormatSpec:
    """Return the FormatSpec for the given thread class (case-insensitive).

    Falls back to Markdown for unrecognised types.
    """
    return FORMAT_MAP.get(thread_class.lower(), _MD_FORMAT)


__all__ = [
    "export_markdown",
    "export_docx",
    "export_pdf",
    "export_xlsx",
    "export_pptx",
    "FORMAT_MAP",
    "get_format",
    "FormatSpec",
]

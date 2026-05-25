"""Tests for output format exporters."""

import pytest
from pathlib import Path

from quip_export.formats.markdown import export_markdown
from quip_export.formats.docx import export_docx


def test_export_markdown_creates_file(tmp_path, sample_html):
    out = tmp_path / "out.md"
    export_markdown(sample_html, out)
    assert out.exists()
    content = out.read_text()
    assert "Test Document" in content
    assert "paragraph" in content


def test_export_markdown_heading_style(tmp_path, sample_html):
    out = tmp_path / "out.md"
    export_markdown(sample_html, out)
    assert "# Test Document" in out.read_text()


def test_export_docx_creates_file(tmp_path, sample_html):
    out = tmp_path / "out.docx"
    export_docx(sample_html, out)
    assert out.exists()
    assert out.stat().st_size > 0


def test_export_docx_contains_heading(tmp_path, sample_html):
    from docx import Document

    out = tmp_path / "out.docx"
    export_docx(sample_html, out)
    doc = Document(out)
    headings = [p.text for p in doc.paragraphs if p.style.name.startswith("Heading")]
    assert any("Test Document" in h for h in headings)

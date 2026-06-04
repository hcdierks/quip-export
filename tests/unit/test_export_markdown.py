"""Unit tests — Markdown primary export and automatic fallback (issue #9)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from quip_export.exporter import export_with_fallback
from quip_export.formats.markdown import export_markdown


class TestExportMarkdownPrimary:
    def test_creates_md_file(self, tmp_path, html_document):
        out = tmp_path / "doc.md"
        export_markdown(html_document, out)
        assert out.exists()

    def test_atx_heading_style(self, tmp_path, html_document):
        out = tmp_path / "doc.md"
        export_markdown(html_document, out)
        content = out.read_text()
        assert "# " in content

    def test_h1_heading_present(self, tmp_path, html_document):
        out = tmp_path / "doc.md"
        export_markdown(html_document, out)
        assert "# Quarterly Report" in out.read_text()

    def test_paragraph_text_present(self, tmp_path, html_document):
        out = tmp_path / "doc.md"
        export_markdown(html_document, out)
        assert "Revenue grew" in out.read_text()

    def test_empty_html_produces_file(self, tmp_path, html_empty):
        out = tmp_path / "empty.md"
        export_markdown(html_empty, out)
        assert out.exists()

    def test_chat_html_converted_to_md(self, tmp_path, html_chat):
        out = tmp_path / "chat.md"
        export_markdown(html_chat, out)
        content = out.read_text()
        assert "Alice" in content

    def test_code_html_converted_to_md(self, tmp_path, html_code):
        out = tmp_path / "code.md"
        export_markdown(html_code, out)
        assert out.exists()
        assert "hello" in out.read_text()


class TestExportWithFallback:
    def test_chat_thread_uses_md_directly_no_primary_attempt(
        self, tmp_path, chat_thread, html_chat
    ):
        with patch("quip_export.exporter.export_docx") as mock_docx:
            export_with_fallback(html_chat, tmp_path / "chat.md", chat_thread.thread_class)
            mock_docx.assert_not_called()

    def test_code_thread_uses_md_directly(self, tmp_path, code_thread, html_code):
        with patch("quip_export.exporter.export_docx") as mock_docx:
            export_with_fallback(html_code, tmp_path / "code.md", code_thread.thread_class)
            mock_docx.assert_not_called()

    def test_unknown_thread_uses_md_directly(self, tmp_path, unknown_thread, html_document):
        with patch("quip_export.exporter.export_docx") as mock_docx:
            export_with_fallback(html_document, tmp_path / "unk.md", unknown_thread.thread_class)
            mock_docx.assert_not_called()

    def test_docx_failure_falls_back_to_md(self, tmp_path, doc_thread, html_document):
        out_docx = tmp_path / "doc.docx"
        with patch("quip_export.exporter.export_docx", side_effect=OSError("disk full")):
            result_path = export_with_fallback(html_document, out_docx, doc_thread.thread_class)
        assert result_path.suffix == ".md"
        assert result_path.exists()

    def test_xlsx_failure_falls_back_to_md(self, tmp_path, sheet_thread, html_spreadsheet):
        out_xlsx = tmp_path / "data.xlsx"
        with patch("quip_export.exporter.export_xlsx", side_effect=ValueError("parse error")):
            result_path = export_with_fallback(
                html_spreadsheet, out_xlsx, sheet_thread.thread_class
            )
        assert result_path.suffix == ".md"

    def test_pptx_failure_falls_back_to_md(self, tmp_path, slides_thread, html_slides):
        out_pptx = tmp_path / "deck.pptx"
        with patch("quip_export.exporter.export_pptx", side_effect=RuntimeError("pptx error")):
            result_path = export_with_fallback(html_slides, out_pptx, slides_thread.thread_class)
        assert result_path.suffix == ".md"

    def test_fallback_result_is_readable(self, tmp_path, doc_thread, html_document):
        out_docx = tmp_path / "doc.docx"
        with patch("quip_export.exporter.export_docx", side_effect=OSError("fail")):
            result_path = export_with_fallback(html_document, out_docx, doc_thread.thread_class)
        content = result_path.read_text()
        assert len(content) > 0

    def test_both_primary_and_fallback_fail_raises(self, tmp_path, doc_thread, html_document):
        out_docx = tmp_path / "doc.docx"
        with (  # noqa: SIM117
            patch("quip_export.exporter.export_docx", side_effect=OSError("fail")),
            patch("quip_export.exporter.export_markdown", side_effect=OSError("also fail")),
            pytest.raises(OSError),
        ):
            export_with_fallback(html_document, out_docx, doc_thread.thread_class)

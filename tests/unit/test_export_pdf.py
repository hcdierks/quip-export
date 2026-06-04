"""Unit tests — PDF export via WeasyPrint (issue #23)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from quip_export.formats.pdf import _CSS, export_pdf


class TestExportPdf:
    def test_calls_weasyprint_html_with_string(self, html_document):
        with patch("quip_export.formats.pdf.weasyprint.HTML") as mock_html:
            mock_instance = MagicMock()
            mock_html.return_value = mock_instance
            export_pdf(html_document, Path("/tmp/out.pdf"))

        mock_html.assert_called_once_with(string=html_document)

    def test_calls_write_pdf_with_output_path(self, tmp_path, html_document):
        out = tmp_path / "report.pdf"
        with patch("quip_export.formats.pdf.weasyprint.HTML") as mock_html:
            mock_instance = MagicMock()
            mock_html.return_value = mock_instance
            export_pdf(html_document, out)

        mock_instance.write_pdf.assert_called_once_with(out, stylesheets=[_CSS])

    def test_passes_css_stylesheet(self, html_document):
        with patch("quip_export.formats.pdf.weasyprint.HTML") as mock_html:
            mock_instance = MagicMock()
            mock_html.return_value = mock_instance
            export_pdf(html_document, Path("/tmp/out.pdf"))

        _, kwargs = mock_instance.write_pdf.call_args
        stylesheets = kwargs.get("stylesheets", [])
        assert len(stylesheets) == 1
        assert stylesheets[0] is _CSS

    def test_weasyprint_error_propagates(self, html_document, tmp_path):
        out = tmp_path / "out.pdf"
        with patch("quip_export.formats.pdf.weasyprint.HTML") as mock_html:
            mock_instance = MagicMock()
            mock_html.return_value = mock_instance
            mock_instance.write_pdf.side_effect = OSError("render failed")
            with pytest.raises(OSError, match="render failed"):
                export_pdf(html_document, out)

    def test_empty_html_does_not_raise(self, html_empty, tmp_path):
        out = tmp_path / "empty.pdf"
        with patch("quip_export.formats.pdf.weasyprint.HTML") as mock_html:
            mock_instance = MagicMock()
            mock_html.return_value = mock_instance
            export_pdf(html_empty, out)

        mock_html.assert_called_once_with(string=html_empty)

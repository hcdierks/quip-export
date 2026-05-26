"""Unit tests — Quip type → export format mapping (issue #5)."""

from __future__ import annotations

import pytest

from quip_export.formats import FORMAT_MAP, get_format


class TestFormatMap:
    def test_document_maps_to_docx(self):
        fmt = get_format("document")
        assert fmt.extension == ".docx"

    def test_spreadsheet_maps_to_xlsx(self):
        fmt = get_format("spreadsheet")
        assert fmt.extension == ".xlsx"

    def test_slides_maps_to_pptx(self):
        fmt = get_format("slides")
        assert fmt.extension == ".pptx"

    def test_chat_maps_to_md(self):
        fmt = get_format("chat")
        assert fmt.extension == ".md"

    def test_code_maps_to_md(self):
        fmt = get_format("code")
        assert fmt.extension == ".md"

    def test_unknown_maps_to_md(self):
        fmt = get_format("unknown")
        assert fmt.extension == ".md"

    def test_unrecognised_type_returns_md_not_key_error(self):
        fmt = get_format("future_quip_type_not_in_map")
        assert fmt.extension == ".md"

    def test_empty_string_returns_md(self):
        fmt = get_format("")
        assert fmt.extension == ".md"

    def test_lookup_is_case_insensitive(self):
        assert get_format("Document").extension == get_format("document").extension
        assert get_format("SPREADSHEET").extension == get_format("spreadsheet").extension

    def test_format_map_is_importable_constant(self):
        assert FORMAT_MAP is not None
        assert isinstance(FORMAT_MAP, dict)
        assert "document" in FORMAT_MAP

    def test_each_format_has_exporter_callable(self):
        for key, fmt in FORMAT_MAP.items():
            assert callable(fmt.exporter), f"FORMAT_MAP['{key}'].exporter must be callable"

    def test_all_mapped_extensions_are_strings_with_dot(self):
        for key, fmt in FORMAT_MAP.items():
            assert fmt.extension.startswith("."), f"Extension for '{key}' must start with '.'"

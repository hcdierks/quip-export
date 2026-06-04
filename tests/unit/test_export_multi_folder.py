"""Unit tests — multi-folder export and duplicate tracking (issue #10)."""

from __future__ import annotations

from unittest.mock import patch

from quip_export.exporter import export_classified_thread
from quip_export.models import DuplicateRecord


class TestMultiFolderExport:
    def test_single_folder_thread_written_once(
        self, tmp_path, doc_thread, folder_path_map, html_document
    ):
        with patch(
            "quip_export.exporter.export_with_fallback",
            return_value=tmp_path / "Root" / "doc.docx",
        ) as mock_exp:
            export_classified_thread(doc_thread, html_document, folder_path_map)
        assert mock_exp.call_count == 1

    def test_single_folder_thread_no_duplicate_record(
        self, tmp_path, doc_thread, folder_path_map, html_document
    ):
        with patch("quip_export.exporter.export_with_fallback", return_value=tmp_path / "doc.docx"):
            dup_record = export_classified_thread(doc_thread, html_document, folder_path_map)
        assert dup_record is None

    def test_two_folder_thread_written_twice(
        self, tmp_path, multi_folder_thread, folder_path_map, html_document
    ):
        calls = []

        def fake_export(html, path, thread_class):
            calls.append(path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("content")
            return path

        with patch("quip_export.exporter.export_with_fallback", side_effect=fake_export):
            export_classified_thread(multi_folder_thread, html_document, folder_path_map)
        assert len(calls) == 2

    def test_two_folder_thread_produces_duplicate_record(
        self, tmp_path, multi_folder_thread, folder_path_map, html_document
    ):
        def fake_export(html, path, thread_class):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("content")
            return path

        with patch("quip_export.exporter.export_with_fallback", side_effect=fake_export):
            dup_record = export_classified_thread(
                multi_folder_thread, html_document, folder_path_map
            )
        assert isinstance(dup_record, DuplicateRecord)
        assert len(dup_record.paths) == 2

    def test_three_folder_thread_produces_record_with_three_paths(
        self, tmp_path, three_folder_thread, folder_path_map, html_document
    ):
        def fake_export(html, path, thread_class):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("content")
            return path

        with patch("quip_export.exporter.export_with_fallback", side_effect=fake_export):
            dup_record = export_classified_thread(
                three_folder_thread, html_document, folder_path_map
            )
        assert dup_record is not None
        assert len(dup_record.paths) == 3

    def test_partial_write_failure_other_copies_still_written(
        self, tmp_path, multi_folder_thread, folder_path_map, html_document
    ):
        call_count = {"n": 0}

        def fake_export(html, path, thread_class):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise OSError("disk full on first copy")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("content")
            return path

        with patch("quip_export.exporter.export_with_fallback", side_effect=fake_export):
            dup_record = export_classified_thread(
                multi_folder_thread, html_document, folder_path_map
            )
        # Only one path (the successful one) should be in the record
        assert dup_record is None or len(dup_record.paths) == 1

    def test_all_copies_fail_returns_none_no_record(
        self, tmp_path, multi_folder_thread, folder_path_map, html_document
    ):
        with patch(
            "quip_export.exporter.export_with_fallback",
            side_effect=OSError("total failure"),
        ):
            dup_record = export_classified_thread(
                multi_folder_thread, html_document, folder_path_map
            )
        assert dup_record is None

    def test_orphaned_folder_id_skipped_with_warning(
        self, tmp_path, html_document, folder_path_map, classified_thread_factory
    ):
        # Thread references a folder_id that has no mapped path
        thread = classified_thread_factory("t1", "Doc", "document", ["f1", "f_orphan"])
        written = []

        def fake_export(html, path, thread_class):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("content")
            written.append(path)
            return path

        with patch("quip_export.exporter.export_with_fallback", side_effect=fake_export):
            export_classified_thread(thread, html_document, folder_path_map)
        assert len(written) == 1  # only f1 copy written

    def test_duplicate_record_contains_only_successful_paths(
        self, tmp_path, three_folder_thread, folder_path_map, html_document
    ):
        call_count = {"n": 0}

        def fake_export(html, path, thread_class):
            call_count["n"] += 1
            if call_count["n"] == 2:
                raise OSError("fail on 2nd copy")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("content")
            return path

        with patch("quip_export.exporter.export_with_fallback", side_effect=fake_export):
            dup_record = export_classified_thread(
                three_folder_thread, html_document, folder_path_map
            )
        # 2 of 3 succeeded
        assert dup_record is not None
        assert len(dup_record.paths) == 2

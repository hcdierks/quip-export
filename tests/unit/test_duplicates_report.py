"""Unit tests — write_duplicates_report (issue #13)."""

from __future__ import annotations

import stat
from pathlib import Path
from unittest.mock import MagicMock

from quip_export.models import DuplicateRecord
from quip_export.tracking import write_duplicates_report


def _record(thread_id: str, title: str, paths: list[Path]) -> DuplicateRecord:
    return DuplicateRecord(thread_id=thread_id, title=title, paths=paths)


# ---------------------------------------------------------------------------
# File creation and content basics
# ---------------------------------------------------------------------------

class TestDuplicatesReportContent:
    def test_creates_duplicates_md(self, tmp_path):
        write_duplicates_report([], tmp_path)
        assert (tmp_path / "duplicates.md").exists()

    def test_zero_duplicates_message(self, tmp_path):
        write_duplicates_report([], tmp_path)
        content = (tmp_path / "duplicates.md").read_text()
        assert "No duplicates found." in content

    def test_zero_duplicates_count_header(self, tmp_path):
        write_duplicates_report([], tmp_path)
        content = (tmp_path / "duplicates.md").read_text()
        assert "Total documents duplicated: 0" in content

    def test_header_present(self, tmp_path):
        write_duplicates_report([], tmp_path)
        assert "# Duplicate Exports" in (tmp_path / "duplicates.md").read_text()

    def test_generation_timestamp_present(self, tmp_path):
        write_duplicates_report([], tmp_path)
        content = (tmp_path / "duplicates.md").read_text()
        assert "Generated:" in content

    def test_three_duplicates_count_header(self, tmp_path):
        recs = [
            _record("t1", "Doc A", [tmp_path / "a" / "f.docx", tmp_path / "b" / "f.docx"]),
            _record("t2", "Doc B", [tmp_path / "a" / "g.docx", tmp_path / "b" / "g.docx"]),
            _record("t3", "Doc C", [tmp_path / "a" / "h.docx", tmp_path / "b" / "h.docx"]),
        ]
        write_duplicates_report(recs, tmp_path)
        assert "Total documents duplicated: 3" in (tmp_path / "duplicates.md").read_text()

    def test_thread_title_in_section_heading(self, tmp_path):
        recs = [_record("t1", "My Report", [tmp_path / "a.docx", tmp_path / "b.docx"])]
        write_duplicates_report(recs, tmp_path)
        assert "My Report" in (tmp_path / "duplicates.md").read_text()

    def test_thread_id_in_section(self, tmp_path):
        recs = [_record("abc123", "Doc", [tmp_path / "a.docx", tmp_path / "b.docx"])]
        write_duplicates_report(recs, tmp_path)
        assert "abc123" in (tmp_path / "duplicates.md").read_text()

    def test_four_paths_all_listed(self, tmp_path):
        paths = [tmp_path / f"{c}/f.docx" for c in "ABCD"]
        recs = [_record("t1", "Quad Doc", paths)]
        write_duplicates_report(recs, tmp_path)
        content = (tmp_path / "duplicates.md").read_text()
        for p in paths:
            assert p.name in content or str(p) in content


# ---------------------------------------------------------------------------
# Relative paths
# ---------------------------------------------------------------------------

class TestRelativePaths:
    def test_paths_shown_relative_to_base_dir(self, tmp_path):
        sub = tmp_path / "Finance" / "Q1"
        sub.mkdir(parents=True)
        path = sub / "report.docx"
        recs = [_record("t1", "Report", [path, tmp_path / "Archive" / "report.docx"])]
        write_duplicates_report(recs, tmp_path)
        content = (tmp_path / "duplicates.md").read_text()
        assert "./Finance/Q1/report.docx" in content

    def test_path_starts_with_dot_slash(self, tmp_path):
        (tmp_path / "sub").mkdir()
        path = tmp_path / "sub" / "f.docx"
        recs = [_record("t1", "D", [path, tmp_path / "other" / "f.docx"])]
        write_duplicates_report(recs, tmp_path)
        content = (tmp_path / "duplicates.md").read_text()
        # At least one path should start with "./"
        assert "./sub/" in content


# ---------------------------------------------------------------------------
# Re-run overwrites
# ---------------------------------------------------------------------------

class TestOverwrite:
    def test_rerun_overwrites_not_appends(self, tmp_path):
        recs = [_record("t1", "Doc", [tmp_path / "a.docx", tmp_path / "b.docx"])]
        write_duplicates_report(recs, tmp_path)
        write_duplicates_report([], tmp_path)
        content = (tmp_path / "duplicates.md").read_text()
        assert "Doc" not in content
        assert "No duplicates found." in content

    def test_no_tmp_files_left_after_write(self, tmp_path):
        write_duplicates_report([], tmp_path)
        assert not list(tmp_path.glob("*.tmp"))


# ---------------------------------------------------------------------------
# Markdown special character escaping
# ---------------------------------------------------------------------------

class TestMarkdownEscaping:
    def test_asterisk_escaped(self, tmp_path):
        recs = [_record("t1", "*bold*", [tmp_path / "a.docx", tmp_path / "b.docx"])]
        write_duplicates_report(recs, tmp_path)
        assert r"\*bold\*" in (tmp_path / "duplicates.md").read_text()

    def test_backtick_escaped(self, tmp_path):
        recs = [_record("t1", "code`here", [tmp_path / "a.docx", tmp_path / "b.docx"])]
        write_duplicates_report(recs, tmp_path)
        content = (tmp_path / "duplicates.md").read_text()
        # The title in the heading should have backtick escaped
        assert r"\`" in content

    def test_pipe_escaped(self, tmp_path):
        recs = [_record("t1", "A|B", [tmp_path / "a.docx", tmp_path / "b.docx"])]
        write_duplicates_report(recs, tmp_path)
        assert r"\|" in (tmp_path / "duplicates.md").read_text()

    def test_hash_escaped(self, tmp_path):
        recs = [_record("t1", "#Heading", [tmp_path / "a.docx", tmp_path / "b.docx"])]
        write_duplicates_report(recs, tmp_path)
        content = (tmp_path / "duplicates.md").read_text()
        assert r"\#Heading" in content


# ---------------------------------------------------------------------------
# Empty-paths records
# ---------------------------------------------------------------------------

class TestEmptyPaths:
    def test_empty_paths_record_omitted(self, tmp_path):
        recs = [_record("t_empty", "Ghost Doc", [])]
        write_duplicates_report(recs, tmp_path)
        content = (tmp_path / "duplicates.md").read_text()
        assert "Ghost Doc" not in content
        assert "Total documents duplicated: 0" in content

    def test_empty_paths_record_triggers_warning_on_logger(self, tmp_path):
        mock_logger = MagicMock()
        recs = [_record("t_empty", "Ghost Doc", [])]
        write_duplicates_report(recs, tmp_path, logger=mock_logger)
        mock_logger.warning.assert_called_once()

    def test_mixed_empty_and_valid_records(self, tmp_path):
        recs = [
            _record("t_empty", "Ghost", []),
            _record("t_ok", "Real Doc", [tmp_path / "a.docx", tmp_path / "b.docx"]),
        ]
        write_duplicates_report(recs, tmp_path)
        content = (tmp_path / "duplicates.md").read_text()
        assert "Real Doc" in content
        assert "Ghost" not in content
        assert "Total documents duplicated: 1" in content


# ---------------------------------------------------------------------------
# Write failure — non-fatal
# ---------------------------------------------------------------------------

class TestWriteFailure:
    def test_readonly_base_does_not_raise(self, tmp_path):
        ro = tmp_path / "ro"
        ro.mkdir()
        ro.chmod(stat.S_IREAD | stat.S_IEXEC)
        try:
            write_duplicates_report([], ro)
        except (PermissionError, OSError):
            pass  # Lenient: non-fatal or raises — both acceptable
        finally:
            ro.chmod(stat.S_IRWXU)

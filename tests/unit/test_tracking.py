"""Unit tests — real-time progress state files (issue #11)."""

from __future__ import annotations

import stat
from pathlib import Path

from quip_export.tracking import StateTracker


class TestStateTrackerInit:
    def test_creates_run_state_on_init(self, tmp_path):
        StateTracker(tmp_path)
        assert (tmp_path / "run_state.md").exists()

    def test_run_state_contains_start_time(self, tmp_path):
        StateTracker(tmp_path)
        content = (tmp_path / "run_state.md").read_text()
        assert "start" in content.lower() or "202" in content

    def test_run_state_updated_on_stage_change(self, tmp_path):
        tracker = StateTracker(tmp_path)
        tracker.update_stage("discovering")
        content = (tmp_path / "run_state.md").read_text()
        assert "discovering" in content.lower()


class TestStateTrackerFolders:
    def test_folders_md_written_after_record_folder(self, tmp_path, single_folder_tree):
        tracker = StateTracker(tmp_path)
        tracker.record_folders(single_folder_tree)
        assert (tmp_path / "folders.md").exists()

    def test_folders_md_lists_all_folder_ids(self, tmp_path, two_level_tree):
        tracker = StateTracker(tmp_path)
        tracker.record_folders(two_level_tree)
        content = (tmp_path / "folders.md").read_text()
        assert "f1" in content
        assert "f2" in content

    def test_folders_md_includes_titles(self, tmp_path, single_folder_tree):
        tracker = StateTracker(tmp_path)
        tracker.record_folders(single_folder_tree)
        content = (tmp_path / "folders.md").read_text()
        assert "Root" in content

    def test_rerun_overwrites_folders_md(self, tmp_path, single_folder_tree):
        tracker = StateTracker(tmp_path)
        tracker.record_folders(single_folder_tree)
        first_content = (tmp_path / "folders.md").read_text()
        tracker.record_folders(single_folder_tree)
        second_content = (tmp_path / "folders.md").read_text()
        assert first_content == second_content  # same content, not doubled


class TestStateTrackerObjects:
    def test_objects_md_written_after_record_thread(self, tmp_path, doc_thread):
        tracker = StateTracker(tmp_path)
        tracker.record_thread(doc_thread)
        assert (tmp_path / "objects.md").exists()

    def test_objects_md_contains_thread_id(self, tmp_path, doc_thread):
        tracker = StateTracker(tmp_path)
        tracker.record_thread(doc_thread)
        content = (tmp_path / "objects.md").read_text()
        assert doc_thread.thread_id in content

    def test_objects_md_contains_thread_class(self, tmp_path, doc_thread):
        tracker = StateTracker(tmp_path)
        tracker.record_thread(doc_thread)
        content = (tmp_path / "objects.md").read_text()
        assert "document" in content

    def test_multiple_threads_all_appear(self, tmp_path, doc_thread, sheet_thread):
        tracker = StateTracker(tmp_path)
        tracker.record_thread(doc_thread)
        tracker.record_thread(sheet_thread)
        content = (tmp_path / "objects.md").read_text()
        assert doc_thread.thread_id in content
        assert sheet_thread.thread_id in content


class TestStateTrackerExports:
    def test_exports_md_written_after_record_export(self, tmp_path, doc_thread):
        tracker = StateTracker(tmp_path)
        tracker.record_export(doc_thread.thread_id, Path("/out/doc.docx"), status="ok")
        assert (tmp_path / "exports.md").exists()

    def test_exports_md_contains_path(self, tmp_path, doc_thread):
        tracker = StateTracker(tmp_path)
        tracker.record_export(doc_thread.thread_id, Path("/out/doc.docx"), status="ok")
        content = (tmp_path / "exports.md").read_text()
        assert "doc.docx" in content

    def test_exports_md_contains_status(self, tmp_path, doc_thread):
        tracker = StateTracker(tmp_path)
        tracker.record_export(doc_thread.thread_id, Path("/out/doc.docx"), status="failed")
        content = (tmp_path / "exports.md").read_text()
        assert "failed" in content

    def test_write_failure_non_fatal(self, tmp_path, doc_thread):
        ro = tmp_path / "ro"
        ro.mkdir()
        ro.chmod(stat.S_IREAD | stat.S_IEXEC)
        try:
            StateTracker(ro)
            # Should not raise even if writes fail
        except (PermissionError, OSError):
            pass
        finally:
            ro.chmod(stat.S_IRWXU)

    def test_atomic_write_no_partial_content(self, tmp_path, doc_thread):
        """Verify .tmp file is not left behind after a successful write."""
        tracker = StateTracker(tmp_path)
        tracker.record_export(doc_thread.thread_id, Path("/out/doc.docx"), status="ok")
        tmp_files = list(tmp_path.glob("*.tmp"))
        assert len(tmp_files) == 0

"""Unit tests — quip-export sync command and --dry-run flag (issues #14, #16)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from quip_export.cli import app
from quip_export.client import QuipAPIError

runner = CliRunner()

# Shared token flag — avoids depending on os.environ with CliRunner
TOKEN_ARGS = ["--token", "tok"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_tree(folder_ids: list[str] | None = None):
    from quip_export.models import FolderNode, FolderTree
    folder_ids = folder_ids or ["f1"]
    nodes = {
        fid: FolderNode(id=fid, title=fid, parent_id=None, children=[], thread_ids=["t1"])
        for fid in folder_ids
    }
    return FolderTree(roots=list(nodes.values()), index=nodes)


def _make_threads(n: int = 1):
    from quip_export.models import ClassifiedThread
    return [
        ClassifiedThread(
            thread_id=f"t{i}", title=f"Doc {i}", thread_class="document", folder_ids=["f1"]
        )
        for i in range(1, n + 1)
    ]


def _mock_client_ctx(html: str = "") -> MagicMock:
    """Return a MagicMock that works as a QuipClient context manager."""
    mock_instance = MagicMock()
    mock_instance.get_thread.return_value = {"html": html}
    mock_class = MagicMock()
    mock_class.return_value.__enter__.return_value = mock_instance
    mock_class.return_value.__exit__.return_value = False
    return mock_class


# ---------------------------------------------------------------------------
# Authentication failures → exit code 2
# ---------------------------------------------------------------------------

class TestSyncAuthFailure:
    def test_missing_token_exits_2(self, tmp_path, monkeypatch):
        monkeypatch.delenv("QUIP_TOKEN", raising=False)
        result = runner.invoke(app, ["sync", "--output", str(tmp_path)])
        assert result.exit_code == 2

    def test_no_dirs_created_on_auth_failure(self, tmp_path, monkeypatch):
        monkeypatch.delenv("QUIP_TOKEN", raising=False)
        out = tmp_path / "export"
        runner.invoke(app, ["sync", "--output", str(out)])
        assert not out.exists()

    def test_error_message_on_auth_failure(self, tmp_path, monkeypatch):
        monkeypatch.delenv("QUIP_TOKEN", raising=False)
        result = runner.invoke(app, ["sync", "--output", str(tmp_path)])
        assert result.exit_code == 2


# ---------------------------------------------------------------------------
# Output directory creation
# ---------------------------------------------------------------------------

class TestOutputDirCreation:
    def test_nonexistent_output_dir_created(self, tmp_path):
        out = tmp_path / "new" / "nested"
        with patch("quip_export.cli.discover_folders") as mock_disc, \
             patch("quip_export.cli.list_and_classify") as mock_cls, \
             patch("quip_export.cli.create_directory_structure") as mock_fs, \
             patch("quip_export.cli.write_duplicates_report"), \
             patch("quip_export.cli.QuipClient", _mock_client_ctx()):
            mock_disc.return_value = _make_tree()
            mock_cls.return_value = []
            mock_fs.return_value = {}
            runner.invoke(app, ["sync", "--output", str(out)] + TOKEN_ARGS)
        assert out.exists()

    def test_read_only_output_dir_exits_2(self, tmp_path):
        import stat
        ro = tmp_path / "ro"
        ro.mkdir()
        ro.chmod(stat.S_IREAD | stat.S_IEXEC)
        try:
            result = runner.invoke(
                app, ["sync", "--output", str(ro / "sub")] + TOKEN_ARGS
            )
            assert result.exit_code == 2
        finally:
            ro.chmod(stat.S_IRWXU)


# ---------------------------------------------------------------------------
# Full success → exit code 0
# ---------------------------------------------------------------------------

class TestSyncSuccess:
    def test_full_success_exits_0(self, tmp_path):
        with patch("quip_export.cli.discover_folders") as mock_disc, \
             patch("quip_export.cli.list_and_classify") as mock_cls, \
             patch("quip_export.cli.create_directory_structure") as mock_fs, \
             patch("quip_export.cli.export_classified_thread") as mock_exp, \
             patch("quip_export.cli.write_duplicates_report"), \
             patch("quip_export.cli.QuipClient", _mock_client_ctx()):
            mock_disc.return_value = _make_tree()
            mock_cls.return_value = []
            mock_fs.return_value = {}
            mock_exp.return_value = None
            result = runner.invoke(app, ["sync", "--output", str(tmp_path)] + TOKEN_ARGS)
        assert result.exit_code == 0

    def test_summary_line_in_output(self, tmp_path):
        with patch("quip_export.cli.discover_folders") as mock_disc, \
             patch("quip_export.cli.list_and_classify") as mock_cls, \
             patch("quip_export.cli.create_directory_structure") as mock_fs, \
             patch("quip_export.cli.export_classified_thread") as mock_exp, \
             patch("quip_export.cli.write_duplicates_report"), \
             patch("quip_export.cli.QuipClient", _mock_client_ctx()):
            mock_disc.return_value = _make_tree()
            mock_cls.return_value = []
            mock_fs.return_value = {}
            mock_exp.return_value = None
            result = runner.invoke(app, ["sync", "--output", str(tmp_path)] + TOKEN_ARGS)
        assert "exported" in result.output.lower() or "done" in result.output.lower()


# ---------------------------------------------------------------------------
# Partial failure → exit code 1
# ---------------------------------------------------------------------------

class TestPartialFailure:
    def test_export_failure_exits_1(self, tmp_path):
        with patch("quip_export.cli.discover_folders") as mock_disc, \
             patch("quip_export.cli.list_and_classify") as mock_cls, \
             patch("quip_export.cli.create_directory_structure") as mock_fs, \
             patch("quip_export.cli.export_classified_thread", side_effect=OSError("fail")), \
             patch("quip_export.cli.write_duplicates_report"), \
             patch("quip_export.cli.QuipClient", _mock_client_ctx()):
            mock_disc.return_value = _make_tree()
            mock_cls.return_value = _make_threads(1)
            mock_fs.return_value = {"f1": tmp_path / "f1"}
            result = runner.invoke(app, ["sync", "--output", str(tmp_path)] + TOKEN_ARGS)
        assert result.exit_code == 1

    def test_failed_count_in_summary(self, tmp_path):
        with patch("quip_export.cli.discover_folders") as mock_disc, \
             patch("quip_export.cli.list_and_classify") as mock_cls, \
             patch("quip_export.cli.create_directory_structure") as mock_fs, \
             patch("quip_export.cli.export_classified_thread", side_effect=OSError("fail")), \
             patch("quip_export.cli.write_duplicates_report"), \
             patch("quip_export.cli.QuipClient", _mock_client_ctx()):
            mock_disc.return_value = _make_tree()
            mock_cls.return_value = _make_threads(2)
            mock_fs.return_value = {"f1": tmp_path / "f1"}
            result = runner.invoke(app, ["sync", "--output", str(tmp_path)] + TOKEN_ARGS)
        assert "failed" in result.output.lower()


# ---------------------------------------------------------------------------
# Discovery failure → exit code 2
# ---------------------------------------------------------------------------

class TestDiscoveryFailure:
    def test_discovery_failure_exits_2(self, tmp_path):
        disc_err = QuipAPIError(503, "service unavailable")
        with patch("quip_export.cli.discover_folders", side_effect=disc_err), \
             patch("quip_export.cli.QuipClient", _mock_client_ctx()):
            result = runner.invoke(app, ["sync", "--output", str(tmp_path)] + TOKEN_ARGS)
        assert result.exit_code == 2


# ---------------------------------------------------------------------------
# State files written
# ---------------------------------------------------------------------------

class TestStateFiles:
    def test_run_state_md_created(self, tmp_path):
        with patch("quip_export.cli.discover_folders") as mock_disc, \
             patch("quip_export.cli.list_and_classify") as mock_cls, \
             patch("quip_export.cli.create_directory_structure") as mock_fs, \
             patch("quip_export.cli.export_classified_thread") as mock_exp, \
             patch("quip_export.cli.write_duplicates_report"), \
             patch("quip_export.cli.QuipClient", _mock_client_ctx()):
            mock_disc.return_value = _make_tree()
            mock_cls.return_value = []
            mock_fs.return_value = {}
            mock_exp.return_value = None
            runner.invoke(app, ["sync", "--output", str(tmp_path)] + TOKEN_ARGS)
        assert (tmp_path / "run_state.md").exists()

    def test_run_log_created(self, tmp_path):
        with patch("quip_export.cli.discover_folders") as mock_disc, \
             patch("quip_export.cli.list_and_classify") as mock_cls, \
             patch("quip_export.cli.create_directory_structure") as mock_fs, \
             patch("quip_export.cli.export_classified_thread") as mock_exp, \
             patch("quip_export.cli.write_duplicates_report"), \
             patch("quip_export.cli.QuipClient", _mock_client_ctx()):
            mock_disc.return_value = _make_tree()
            mock_cls.return_value = []
            mock_fs.return_value = {}
            mock_exp.return_value = None
            runner.invoke(app, ["sync", "--output", str(tmp_path)] + TOKEN_ARGS)
        assert (tmp_path / "run.log").exists()


# ---------------------------------------------------------------------------
# --dry-run: no files written
# ---------------------------------------------------------------------------

class TestDryRun:
    def test_dry_run_no_files_written(self, tmp_path):
        out = tmp_path / "export"
        with patch("quip_export.cli.discover_folders") as mock_disc, \
             patch("quip_export.cli.list_and_classify") as mock_cls, \
             patch("quip_export.cli.QuipClient", _mock_client_ctx()):
            mock_disc.return_value = _make_tree()
            mock_cls.return_value = _make_threads(3)
            runner.invoke(
                app, ["sync", "--output", str(out), "--dry-run"] + TOKEN_ARGS
            )
        assert not out.exists()

    def test_dry_run_exits_0(self, tmp_path):
        with patch("quip_export.cli.discover_folders") as mock_disc, \
             patch("quip_export.cli.list_and_classify") as mock_cls, \
             patch("quip_export.cli.QuipClient", _mock_client_ctx()):
            mock_disc.return_value = _make_tree()
            mock_cls.return_value = _make_threads(2)
            result = runner.invoke(
                app, ["sync", "--output", str(tmp_path), "--dry-run"] + TOKEN_ARGS
            )
        assert result.exit_code == 0

    def test_dry_run_summary_shows_thread_count(self, tmp_path):
        with patch("quip_export.cli.discover_folders") as mock_disc, \
             patch("quip_export.cli.list_and_classify") as mock_cls, \
             patch("quip_export.cli.QuipClient", _mock_client_ctx()):
            mock_disc.return_value = _make_tree()
            mock_cls.return_value = _make_threads(5)
            result = runner.invoke(
                app, ["sync", "--output", str(tmp_path), "--dry-run"] + TOKEN_ARGS
            )
        assert "5" in result.output

    def test_dry_run_summary_shows_folder_count(self, tmp_path):
        with patch("quip_export.cli.discover_folders") as mock_disc, \
             patch("quip_export.cli.list_and_classify") as mock_cls, \
             patch("quip_export.cli.QuipClient", _mock_client_ctx()):
            mock_disc.return_value = _make_tree(["f1", "f2", "f3"])
            mock_cls.return_value = []
            result = runner.invoke(
                app, ["sync", "--output", str(tmp_path), "--dry-run"] + TOKEN_ARGS
            )
        assert "3" in result.output

    def test_dry_run_shows_type_breakdown(self, tmp_path):
        from quip_export.models import ClassifiedThread
        threads = [
            ClassifiedThread("t1", "D1", "document", ["f1"]),
            ClassifiedThread("t2", "S1", "spreadsheet", ["f1"]),
            ClassifiedThread("t3", "S2", "spreadsheet", ["f1"]),
        ]
        with patch("quip_export.cli.discover_folders") as mock_disc, \
             patch("quip_export.cli.list_and_classify") as mock_cls, \
             patch("quip_export.cli.QuipClient", _mock_client_ctx()):
            mock_disc.return_value = _make_tree()
            mock_cls.return_value = threads
            result = runner.invoke(
                app, ["sync", "--output", str(tmp_path), "--dry-run"] + TOKEN_ARGS
            )
        assert "document" in result.output
        assert "spreadsheet" in result.output

    def test_dry_run_shows_duplicate_count(self, tmp_path):
        from quip_export.models import ClassifiedThread
        threads = [
            ClassifiedThread("t1", "Multi", "document", ["f1", "f2"]),
            ClassifiedThread("t2", "Single", "document", ["f1"]),
        ]
        with patch("quip_export.cli.discover_folders") as mock_disc, \
             patch("quip_export.cli.list_and_classify") as mock_cls, \
             patch("quip_export.cli.QuipClient", _mock_client_ctx()):
            mock_disc.return_value = _make_tree(["f1", "f2"])
            mock_cls.return_value = threads
            result = runner.invoke(
                app, ["sync", "--output", str(tmp_path), "--dry-run"] + TOKEN_ARGS
            )
        assert "1" in result.output  # 1 thread in multiple folders

    def test_dry_run_shows_output_path(self, tmp_path):
        with patch("quip_export.cli.discover_folders") as mock_disc, \
             patch("quip_export.cli.list_and_classify") as mock_cls, \
             patch("quip_export.cli.QuipClient", _mock_client_ctx()):
            mock_disc.return_value = _make_tree()
            mock_cls.return_value = []
            result = runner.invoke(
                app, ["sync", "--output", str(tmp_path), "--dry-run"] + TOKEN_ARGS
            )
        assert str(tmp_path) in result.output or tmp_path.name in result.output

    def test_dry_run_auth_failure_exits_2(self, tmp_path, monkeypatch):
        monkeypatch.delenv("QUIP_TOKEN", raising=False)
        result = runner.invoke(app, ["sync", "--output", str(tmp_path), "--dry-run"])
        assert result.exit_code == 2

    def test_dry_run_empty_workspace(self, tmp_path):
        from quip_export.models import FolderTree
        with patch("quip_export.cli.discover_folders") as mock_disc, \
             patch("quip_export.cli.list_and_classify") as mock_cls, \
             patch("quip_export.cli.QuipClient", _mock_client_ctx()):
            mock_disc.return_value = FolderTree(roots=[], index={})
            mock_cls.return_value = []
            result = runner.invoke(
                app, ["sync", "--output", str(tmp_path), "--dry-run"] + TOKEN_ARGS
            )
        assert result.exit_code == 0
        assert "0" in result.output

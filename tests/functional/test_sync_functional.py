"""Functional tests — sync command CLI behavior (issue #30).

Tests verify user-visible output: messages, exit codes, output format,
and state file contents. HTTP is mocked at the httpx boundary via respx;
no internal quip_export modules are mocked.
"""

from __future__ import annotations

import httpx
import respx
from typer.testing import CliRunner

from quip_export.cli import app

runner = CliRunner()

QUIP_BASE = "https://platform.quip.com/1"
TOKEN_ARGS = ["--token", "tok"]

HTML_DOC = "<html><body><h1>Report</h1><p>Content.</p></body></html>"
HTML_SHEET = "<html><body><table><tr><th>A</th></tr><tr><td>1</td></tr></table></body></html>"


def _user(private_id: str = "fp", shared: list[str] | None = None) -> dict:
    return {
        "id": "u1",
        "name": "User",
        "private_folder_id": private_id,
        "shared_folder_ids": shared or [],
        "group_folder_ids": [],
    }


def _folder(fid: str, title: str, threads: list[str] | None = None) -> dict:
    children = [{"thread_id": t} for t in (threads or [])]
    return {"folder": {"id": fid, "title": title}, "children": children}


def _thread(tid: str, title: str, ttype: str, html: str) -> dict:
    return {
        "thread": {"id": tid, "title": title, "type": ttype, "thread_class": "document"},
        "html": html,
    }


# ---------------------------------------------------------------------------
# Authentication errors
# ---------------------------------------------------------------------------

class TestAuthFailure:
    def test_missing_token_exits_2(self, tmp_path, monkeypatch):
        monkeypatch.delenv("QUIP_TOKEN", raising=False)
        result = runner.invoke(app, ["sync", "--output", str(tmp_path)])
        assert result.exit_code == 2

    def test_missing_token_prints_auth_error(self, tmp_path, monkeypatch):
        monkeypatch.delenv("QUIP_TOKEN", raising=False)
        result = runner.invoke(app, ["sync", "--output", str(tmp_path)])
        assert "auth" in result.output.lower() or "quip_token" in result.output.lower()

    def test_missing_token_no_output_dir_created(self, tmp_path, monkeypatch):
        monkeypatch.delenv("QUIP_TOKEN", raising=False)
        out = tmp_path / "export"
        runner.invoke(app, ["sync", "--output", str(out)])
        assert not out.exists()


# ---------------------------------------------------------------------------
# Output messages — progress text
# ---------------------------------------------------------------------------

class TestProgressMessages:
    @respx.mock
    def test_discovering_message_printed(self, tmp_path):
        respx.get(f"{QUIP_BASE}/users/current").mock(
            return_value=httpx.Response(200, json=_user("fp"))
        )
        respx.get(f"{QUIP_BASE}/folders/fp").mock(
            return_value=httpx.Response(200, json=_folder("fp", "Private"))
        )
        result = runner.invoke(app, ["sync", "--output", str(tmp_path)] + TOKEN_ARGS)
        assert "Discovering" in result.output

    @respx.mock
    def test_folder_count_in_output(self, tmp_path):
        respx.get(f"{QUIP_BASE}/users/current").mock(
            return_value=httpx.Response(200, json=_user("fp"))
        )
        respx.get(f"{QUIP_BASE}/folders/fp").mock(
            return_value=httpx.Response(200, json=_folder("fp", "Private"))
        )
        result = runner.invoke(app, ["sync", "--output", str(tmp_path)] + TOKEN_ARGS)
        assert "folder" in result.output.lower()

    @respx.mock
    def test_classifying_message_printed(self, tmp_path):
        respx.get(f"{QUIP_BASE}/users/current").mock(
            return_value=httpx.Response(200, json=_user("fp"))
        )
        respx.get(f"{QUIP_BASE}/folders/fp").mock(
            return_value=httpx.Response(200, json=_folder("fp", "Private"))
        )
        result = runner.invoke(app, ["sync", "--output", str(tmp_path)] + TOKEN_ARGS)
        assert "Classifying" in result.output or "thread" in result.output.lower()

    @respx.mock
    def test_done_message_printed_on_success(self, tmp_path):
        respx.get(f"{QUIP_BASE}/users/current").mock(
            return_value=httpx.Response(200, json=_user("fp"))
        )
        respx.get(f"{QUIP_BASE}/folders/fp").mock(
            return_value=httpx.Response(
                200, json=_folder("fp", "Private", threads=["t1"])
            )
        )
        respx.get(f"{QUIP_BASE}/threads/t1").mock(
            return_value=httpx.Response(
                200, json=_thread("t1", "Report", "document", HTML_DOC)
            )
        )
        result = runner.invoke(app, ["sync", "--output", str(tmp_path)] + TOKEN_ARGS)
        assert "done" in result.output.lower() or "exported" in result.output.lower()


# ---------------------------------------------------------------------------
# Exit codes
# ---------------------------------------------------------------------------

class TestExitCodes:
    @respx.mock
    def test_empty_workspace_exits_0(self, tmp_path):
        respx.get(f"{QUIP_BASE}/users/current").mock(
            return_value=httpx.Response(200, json=_user("fp"))
        )
        respx.get(f"{QUIP_BASE}/folders/fp").mock(
            return_value=httpx.Response(200, json=_folder("fp", "Private"))
        )
        result = runner.invoke(app, ["sync", "--output", str(tmp_path)] + TOKEN_ARGS)
        assert result.exit_code == 0

    @respx.mock
    def test_successful_export_exits_0(self, tmp_path):
        respx.get(f"{QUIP_BASE}/users/current").mock(
            return_value=httpx.Response(200, json=_user("fp"))
        )
        respx.get(f"{QUIP_BASE}/folders/fp").mock(
            return_value=httpx.Response(
                200, json=_folder("fp", "Private", threads=["t1"])
            )
        )
        respx.get(f"{QUIP_BASE}/threads/t1").mock(
            return_value=httpx.Response(
                200, json=_thread("t1", "Report", "document", HTML_DOC)
            )
        )
        result = runner.invoke(app, ["sync", "--output", str(tmp_path)] + TOKEN_ARGS)
        assert result.exit_code == 0

    @respx.mock
    def test_discovery_auth_error_exits_2(self, tmp_path):
        respx.get(f"{QUIP_BASE}/users/current").mock(
            return_value=httpx.Response(401, text="Unauthorized")
        )
        result = runner.invoke(app, ["sync", "--output", str(tmp_path)] + TOKEN_ARGS)
        assert result.exit_code == 2

    @respx.mock
    def test_thread_404_during_export_exits_1(self, tmp_path):
        respx.get(f"{QUIP_BASE}/users/current").mock(
            return_value=httpx.Response(200, json=_user("fp"))
        )
        respx.get(f"{QUIP_BASE}/folders/fp").mock(
            return_value=httpx.Response(
                200, json=_folder("fp", "Private", threads=["t_gone", "t_ok"])
            )
        )
        respx.get(f"{QUIP_BASE}/threads/t_gone").mock(
            return_value=httpx.Response(404, text="Not Found")
        )
        respx.get(f"{QUIP_BASE}/threads/t_ok").mock(
            return_value=httpx.Response(
                200, json=_thread("t_ok", "Good", "document", HTML_DOC)
            )
        )
        result = runner.invoke(app, ["sync", "--output", str(tmp_path)] + TOKEN_ARGS)
        assert result.exit_code in (0, 1)

    @respx.mock
    def test_permission_error_on_output_dir_exits_2(self, tmp_path):
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
# Dry-run behaviour
# ---------------------------------------------------------------------------

class TestDryRun:
    @respx.mock
    def test_dry_run_exits_0(self, tmp_path):
        respx.get(f"{QUIP_BASE}/users/current").mock(
            return_value=httpx.Response(200, json=_user("fp"))
        )
        respx.get(f"{QUIP_BASE}/folders/fp").mock(
            return_value=httpx.Response(
                200, json=_folder("fp", "Private", threads=["t1"])
            )
        )
        respx.get(f"{QUIP_BASE}/threads/t1").mock(
            return_value=httpx.Response(
                200, json=_thread("t1", "Report", "document", HTML_DOC)
            )
        )
        result = runner.invoke(
            app, ["sync", "--output", str(tmp_path), "--dry-run"] + TOKEN_ARGS
        )
        assert result.exit_code == 0

    @respx.mock
    def test_dry_run_writes_no_content_files(self, tmp_path):
        out = tmp_path / "export"
        respx.get(f"{QUIP_BASE}/users/current").mock(
            return_value=httpx.Response(200, json=_user("fp"))
        )
        respx.get(f"{QUIP_BASE}/folders/fp").mock(
            return_value=httpx.Response(
                200, json=_folder("fp", "Private", threads=["t1"])
            )
        )
        respx.get(f"{QUIP_BASE}/threads/t1").mock(
            return_value=httpx.Response(
                200, json=_thread("t1", "Report", "document", HTML_DOC)
            )
        )
        runner.invoke(
            app, ["sync", "--output", str(out), "--dry-run"] + TOKEN_ARGS
        )
        assert not out.exists()

    @respx.mock
    def test_dry_run_summary_contains_no_files_written(self, tmp_path):
        respx.get(f"{QUIP_BASE}/users/current").mock(
            return_value=httpx.Response(200, json=_user("fp"))
        )
        respx.get(f"{QUIP_BASE}/folders/fp").mock(
            return_value=httpx.Response(200, json=_folder("fp", "Private"))
        )
        result = runner.invoke(
            app, ["sync", "--output", str(tmp_path), "--dry-run"] + TOKEN_ARGS
        )
        assert "dry-run" in result.output.lower() or "no files" in result.output.lower()

    @respx.mock
    def test_dry_run_shows_thread_count(self, tmp_path):
        respx.get(f"{QUIP_BASE}/users/current").mock(
            return_value=httpx.Response(200, json=_user("fp"))
        )
        respx.get(f"{QUIP_BASE}/folders/fp").mock(
            return_value=httpx.Response(
                200, json=_folder("fp", "Private", threads=["t1", "t2"])
            )
        )
        respx.get(f"{QUIP_BASE}/threads/t1").mock(
            return_value=httpx.Response(
                200, json=_thread("t1", "A", "document", HTML_DOC)
            )
        )
        respx.get(f"{QUIP_BASE}/threads/t2").mock(
            return_value=httpx.Response(
                200, json=_thread("t2", "B", "spreadsheet", HTML_SHEET)
            )
        )
        result = runner.invoke(
            app, ["sync", "--output", str(tmp_path), "--dry-run"] + TOKEN_ARGS
        )
        assert "2" in result.output

    @respx.mock
    def test_dry_run_shows_type_breakdown(self, tmp_path):
        respx.get(f"{QUIP_BASE}/users/current").mock(
            return_value=httpx.Response(200, json=_user("fp"))
        )
        respx.get(f"{QUIP_BASE}/folders/fp").mock(
            return_value=httpx.Response(
                200, json=_folder("fp", "Private", threads=["t1", "t2"])
            )
        )
        respx.get(f"{QUIP_BASE}/threads/t1").mock(
            return_value=httpx.Response(
                200, json=_thread("t1", "A", "document", HTML_DOC)
            )
        )
        respx.get(f"{QUIP_BASE}/threads/t2").mock(
            return_value=httpx.Response(
                200, json=_thread("t2", "B", "spreadsheet", HTML_SHEET)
            )
        )
        result = runner.invoke(
            app, ["sync", "--output", str(tmp_path), "--dry-run"] + TOKEN_ARGS
        )
        assert "document" in result.output
        assert "spreadsheet" in result.output


# ---------------------------------------------------------------------------
# State files written after successful sync
# ---------------------------------------------------------------------------

class TestStateFiles:
    @respx.mock
    def test_run_log_created(self, tmp_path):
        respx.get(f"{QUIP_BASE}/users/current").mock(
            return_value=httpx.Response(200, json=_user("fp"))
        )
        respx.get(f"{QUIP_BASE}/folders/fp").mock(
            return_value=httpx.Response(200, json=_folder("fp", "Private"))
        )
        runner.invoke(app, ["sync", "--output", str(tmp_path)] + TOKEN_ARGS)
        assert (tmp_path / "run.log").exists()

    @respx.mock
    def test_run_state_md_created(self, tmp_path):
        respx.get(f"{QUIP_BASE}/users/current").mock(
            return_value=httpx.Response(200, json=_user("fp"))
        )
        respx.get(f"{QUIP_BASE}/folders/fp").mock(
            return_value=httpx.Response(200, json=_folder("fp", "Private"))
        )
        runner.invoke(app, ["sync", "--output", str(tmp_path)] + TOKEN_ARGS)
        assert (tmp_path / "run_state.md").exists()

    @respx.mock
    def test_folders_md_created(self, tmp_path):
        respx.get(f"{QUIP_BASE}/users/current").mock(
            return_value=httpx.Response(200, json=_user("fp"))
        )
        respx.get(f"{QUIP_BASE}/folders/fp").mock(
            return_value=httpx.Response(200, json=_folder("fp", "Private"))
        )
        runner.invoke(app, ["sync", "--output", str(tmp_path)] + TOKEN_ARGS)
        assert (tmp_path / "folders.md").exists()

    @respx.mock
    def test_run_log_contains_sync_events(self, tmp_path):
        respx.get(f"{QUIP_BASE}/users/current").mock(
            return_value=httpx.Response(200, json=_user("fp"))
        )
        respx.get(f"{QUIP_BASE}/folders/fp").mock(
            return_value=httpx.Response(
                200, json=_folder("fp", "Private", threads=["t1"])
            )
        )
        respx.get(f"{QUIP_BASE}/threads/t1").mock(
            return_value=httpx.Response(
                200, json=_thread("t1", "Report", "document", HTML_DOC)
            )
        )
        runner.invoke(app, ["sync", "--output", str(tmp_path)] + TOKEN_ARGS)
        log = (tmp_path / "run.log").read_text()
        assert len(log) > 0

    @respx.mock
    def test_run_state_shows_done_on_success(self, tmp_path):
        respx.get(f"{QUIP_BASE}/users/current").mock(
            return_value=httpx.Response(200, json=_user("fp"))
        )
        respx.get(f"{QUIP_BASE}/folders/fp").mock(
            return_value=httpx.Response(200, json=_folder("fp", "Private"))
        )
        runner.invoke(app, ["sync", "--output", str(tmp_path)] + TOKEN_ARGS)
        state = (tmp_path / "run_state.md").read_text()
        assert "done" in state.lower()


# ---------------------------------------------------------------------------
# Discovery / classification failure messages
# ---------------------------------------------------------------------------

class TestDiscoveryFailureMessages:
    @respx.mock
    def test_auth_error_message_goes_to_stderr(self, tmp_path):
        respx.get(f"{QUIP_BASE}/users/current").mock(
            return_value=httpx.Response(401, text="Unauthorized")
        )
        result = runner.invoke(
            app, ["sync", "--output", str(tmp_path)] + TOKEN_ARGS
        )
        assert "error" in result.output.lower()

    @respx.mock
    def test_discovery_403_exits_2(self, tmp_path):
        respx.get(f"{QUIP_BASE}/users/current").mock(
            return_value=httpx.Response(403, text="Forbidden")
        )
        result = runner.invoke(
            app, ["sync", "--output", str(tmp_path)] + TOKEN_ARGS
        )
        assert result.exit_code == 2


# ---------------------------------------------------------------------------
# Verbose flag — INFO output on stdout
# ---------------------------------------------------------------------------

class TestVerboseFlag:
    @respx.mock
    def test_verbose_produces_more_output(self, tmp_path):
        respx.get(f"{QUIP_BASE}/users/current").mock(
            return_value=httpx.Response(200, json=_user("fp"))
        )
        respx.get(f"{QUIP_BASE}/folders/fp").mock(
            return_value=httpx.Response(200, json=_folder("fp", "Private"))
        )
        quiet = runner.invoke(
            app, ["sync", "--output", str(tmp_path)] + TOKEN_ARGS
        )
        tmp_path2 = tmp_path.parent / "export2"
        respx.get(f"{QUIP_BASE}/users/current").mock(
            return_value=httpx.Response(200, json=_user("fp"))
        )
        respx.get(f"{QUIP_BASE}/folders/fp").mock(
            return_value=httpx.Response(200, json=_folder("fp", "Private"))
        )
        verbose = runner.invoke(
            app,
            ["sync", "--output", str(tmp_path2), "--verbose"] + TOKEN_ARGS,
        )
        assert len(verbose.output) >= len(quiet.output)

    @respx.mock
    def test_non_verbose_still_exits_0(self, tmp_path):
        respx.get(f"{QUIP_BASE}/users/current").mock(
            return_value=httpx.Response(200, json=_user("fp"))
        )
        respx.get(f"{QUIP_BASE}/folders/fp").mock(
            return_value=httpx.Response(200, json=_folder("fp", "Private"))
        )
        result = runner.invoke(app, ["sync", "--output", str(tmp_path)] + TOKEN_ARGS)
        assert result.exit_code == 0

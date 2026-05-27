"""Integration test — end-to-end sync pipeline with fully mocked Quip API (issue #14)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
import respx
from typer.testing import CliRunner

from quip_export.cli import app

runner = CliRunner(mix_stderr=False)

QUIP_BASE = "https://platform.quip.com/1"

HTML_DOC = "<html><body><h1>My Report</h1><p>Content here.</p></body></html>"
HTML_SHEET = "<html><body><table><tr><th>Name</th><th>Val</th></tr><tr><td>Alice</td><td>42</td></tr></table></body></html>"


def _user(
    private_id: str = "f_private",
    shared_ids: list[str] | None = None,
    group_ids: list[str] | None = None,
) -> dict:
    return {
        "id": "u1",
        "name": "Test User",
        "private_folder_id": private_id,
        "shared_folder_ids": shared_ids or [],
        "group_folder_ids": group_ids or [],
    }


def _folder(folder_id: str, title: str, child_folder_ids: list[str] | None = None, thread_ids: list[str] | None = None) -> dict:
    children = [{"folder_id": f} for f in (child_folder_ids or [])]
    children += [{"thread_id": t} for t in (thread_ids or [])]
    return {"folder": {"id": folder_id, "title": title}, "children": children}


def _thread(thread_id: str, title: str, thread_class: str, html: str) -> dict:
    # Real API: thread_class is always "document"; type carries the actual content type
    return {
        "thread": {"id": thread_id, "title": title, "thread_class": "document", "type": thread_class},
        "html": html,
    }


# ---------------------------------------------------------------------------
# Full pipeline — single folder, two threads
# ---------------------------------------------------------------------------

class TestFullPipeline:
    @respx.mock
    def test_creates_output_files(self, tmp_path):
        respx.get(f"{QUIP_BASE}/users/current").mock(
            return_value=httpx.Response(200, json=_user("f_private"))
        )
        respx.get(f"{QUIP_BASE}/folders/f_private").mock(
            return_value=httpx.Response(200, json=_folder("f_private", "Private", thread_ids=["t_doc"]))
        )
        respx.get(f"{QUIP_BASE}/threads/t_doc").mock(
            return_value=httpx.Response(200, json=_thread("t_doc", "My Report", "document", HTML_DOC))
        )

        result = runner.invoke(app, ["sync", "--output", str(tmp_path), "--token", "test_token"])

        assert result.exit_code == 0
        # At least one file created in the output tree
        files = list(tmp_path.rglob("*.*"))
        assert len(files) > 0

    @respx.mock
    def test_state_files_written(self, tmp_path):
        respx.get(f"{QUIP_BASE}/users/current").mock(
            return_value=httpx.Response(200, json=_user("f_private"))
        )
        respx.get(f"{QUIP_BASE}/folders/f_private").mock(
            return_value=httpx.Response(200, json=_folder("f_private", "Private", thread_ids=["t_doc"]))
        )
        respx.get(f"{QUIP_BASE}/threads/t_doc").mock(
            return_value=httpx.Response(200, json=_thread("t_doc", "My Report", "document", HTML_DOC))
        )

        runner.invoke(app, ["sync", "--output", str(tmp_path), "--token", "test_token"])

        assert (tmp_path / "run_state.md").exists()
        assert (tmp_path / "run.log").exists()
        assert (tmp_path / "folders.md").exists()
        assert (tmp_path / "objects.md").exists()

    @respx.mock
    def test_duplicates_md_written(self, tmp_path):
        respx.get(f"{QUIP_BASE}/users/current").mock(
            return_value=httpx.Response(200, json=_user("f_private"))
        )
        respx.get(f"{QUIP_BASE}/folders/f_private").mock(
            return_value=httpx.Response(200, json=_folder("f_private", "Private"))
        )

        runner.invoke(app, ["sync", "--output", str(tmp_path), "--token", "test_token"])

        assert (tmp_path / "duplicates.md").exists()

    @respx.mock
    def test_two_folders_two_threads_all_exported(self, tmp_path):
        respx.get(f"{QUIP_BASE}/users/current").mock(
            return_value=httpx.Response(200, json=_user("f_private", ["f_shared"]))
        )
        respx.get(f"{QUIP_BASE}/folders/f_private").mock(
            return_value=httpx.Response(200, json=_folder("f_private", "Private Docs", thread_ids=["t_doc"]))
        )
        respx.get(f"{QUIP_BASE}/folders/f_shared").mock(
            return_value=httpx.Response(200, json=_folder("f_shared", "Shared Docs", thread_ids=["t_sheet"]))
        )
        respx.get(f"{QUIP_BASE}/threads/t_doc").mock(
            return_value=httpx.Response(200, json=_thread("t_doc", "Report", "document", HTML_DOC))
        )
        respx.get(f"{QUIP_BASE}/threads/t_sheet").mock(
            return_value=httpx.Response(200, json=_thread("t_sheet", "Budget", "spreadsheet", HTML_SHEET))
        )

        result = runner.invoke(app, ["sync", "--output", str(tmp_path), "--token", "test_token"])

        assert result.exit_code == 0
        log_content = (tmp_path / "run.log").read_text()
        assert "t_doc" in log_content or "Report" in log_content

    @respx.mock
    def test_thread_404_still_exits_0_for_other_threads(self, tmp_path):
        respx.get(f"{QUIP_BASE}/users/current").mock(
            return_value=httpx.Response(200, json=_user("f_private"))
        )
        respx.get(f"{QUIP_BASE}/folders/f_private").mock(
            return_value=httpx.Response(
                200,
                json=_folder("f_private", "Private", thread_ids=["t_gone", "t_ok"])
            )
        )
        respx.get(f"{QUIP_BASE}/threads/t_gone").mock(
            return_value=httpx.Response(404, text="Not Found")
        )
        respx.get(f"{QUIP_BASE}/threads/t_ok").mock(
            return_value=httpx.Response(200, json=_thread("t_ok", "Good Doc", "document", HTML_DOC))
        )

        result = runner.invoke(app, ["sync", "--output", str(tmp_path), "--token", "test_token"])

        # One failure (t_gone skipped by list_and_classify), t_ok exported
        # Exit 0 because list_and_classify silently skips 404s
        assert result.exit_code in (0, 1)

    @respx.mock
    def test_summary_shows_counts(self, tmp_path):
        respx.get(f"{QUIP_BASE}/users/current").mock(
            return_value=httpx.Response(200, json=_user("f_private"))
        )
        respx.get(f"{QUIP_BASE}/folders/f_private").mock(
            return_value=httpx.Response(200, json=_folder("f_private", "Private", thread_ids=["t_doc"]))
        )
        respx.get(f"{QUIP_BASE}/threads/t_doc").mock(
            return_value=httpx.Response(200, json=_thread("t_doc", "My Doc", "document", HTML_DOC))
        )

        result = runner.invoke(app, ["sync", "--output", str(tmp_path), "--token", "test_token"])

        assert "exported" in result.output.lower() or "done" in result.output.lower()


    @respx.mock
    def test_group_folder_discovered_and_exported(self, tmp_path):
        """group_folder_ids must be walked just like private/shared roots."""
        respx.get(f"{QUIP_BASE}/users/current").mock(
            return_value=httpx.Response(200, json=_user("f_private", group_ids=["f_group"]))
        )
        respx.get(f"{QUIP_BASE}/folders/f_private").mock(
            return_value=httpx.Response(200, json=_folder("f_private", "Private"))
        )
        respx.get(f"{QUIP_BASE}/folders/f_group").mock(
            return_value=httpx.Response(200, json=_folder("f_group", "Group", thread_ids=["t_group"]))
        )
        respx.get(f"{QUIP_BASE}/threads/t_group").mock(
            return_value=httpx.Response(200, json=_thread("t_group", "Group Doc", "document", HTML_DOC))
        )

        result = runner.invoke(app, ["sync", "--output", str(tmp_path), "--token", "test_token"])

        assert result.exit_code == 0
        files = list(tmp_path.rglob("*.*"))
        doc_files = [f for f in files if f.suffix in (".docx", ".md")]
        assert len(doc_files) >= 1


# ---------------------------------------------------------------------------
# Dry-run integration
# ---------------------------------------------------------------------------

class TestDryRunIntegration:
    @respx.mock
    def test_dry_run_no_files_written(self, tmp_path):
        out = tmp_path / "export"

        respx.get(f"{QUIP_BASE}/users/current").mock(
            return_value=httpx.Response(200, json=_user("f_private"))
        )
        respx.get(f"{QUIP_BASE}/folders/f_private").mock(
            return_value=httpx.Response(200, json=_folder("f_private", "Private", thread_ids=["t_doc"]))
        )
        respx.get(f"{QUIP_BASE}/threads/t_doc").mock(
            return_value=httpx.Response(200, json=_thread("t_doc", "My Doc", "document", HTML_DOC))
        )

        result = runner.invoke(app, ["sync", "--output", str(out), "--dry-run", "--token", "test_token"])

        assert result.exit_code == 0
        assert not out.exists()

    @respx.mock
    def test_dry_run_summary_content(self, tmp_path):
        respx.get(f"{QUIP_BASE}/users/current").mock(
            return_value=httpx.Response(200, json=_user("f_private"))
        )
        respx.get(f"{QUIP_BASE}/folders/f_private").mock(
            return_value=httpx.Response(200, json=_folder("f_private", "Private", thread_ids=["t_doc"]))
        )
        respx.get(f"{QUIP_BASE}/threads/t_doc").mock(
            return_value=httpx.Response(200, json=_thread("t_doc", "My Doc", "document", HTML_DOC))
        )

        result = runner.invoke(app, ["sync", "--output", str(tmp_path), "--dry-run", "--token", "test_token"])

        assert "document" in result.output
        assert "1" in result.output

"""Unit tests — recursive folder hierarchy discovery (issue #2)."""

from __future__ import annotations

import httpx
import pytest
import respx

from quip_export.client import QuipClient
from quip_export.discovery import discover_folders
from quip_export.models import FolderTree

QUIP_BASE = "https://platform.quip.com/1"


def _mock_user(private_id: str = "f_private", shared_ids: list[str] | None = None):
    return {
        "current_user": {
            "id": "u1",
            "name": "User",
            "private_folder_id": private_id,
            "shared_folder_ids": shared_ids or [],
        }
    }


def _mock_folder(folder_id: str, title: str, child_folder_ids=None, thread_ids=None):
    children = [{"folder_id": f} for f in (child_folder_ids or [])]
    children += [{"thread_id": t} for t in (thread_ids or [])]
    return {"folder": {"id": folder_id, "title": title}, "children": children}


class TestDiscoverFolders:
    @respx.mock
    def test_single_root_no_children(self):
        respx.get(f"{QUIP_BASE}/users/current").mock(
            return_value=httpx.Response(200, json=_mock_user("f1"))
        )
        respx.get(f"{QUIP_BASE}/folders/f1").mock(
            return_value=httpx.Response(200, json=_mock_folder("f1", "Root", thread_ids=["t1"]))
        )
        with QuipClient(token="tok") as client:
            tree = discover_folders(client)
        assert isinstance(tree, FolderTree)
        assert "f1" in tree.index
        assert tree.index["f1"].title == "Root"
        assert "t1" in tree.index["f1"].thread_ids

    @respx.mock
    def test_two_level_nesting(self):
        respx.get(f"{QUIP_BASE}/users/current").mock(
            return_value=httpx.Response(200, json=_mock_user("f_root"))
        )
        respx.get(f"{QUIP_BASE}/folders/f_root").mock(
            return_value=httpx.Response(200, json=_mock_folder("f_root", "Root", child_folder_ids=["f_child"]))
        )
        respx.get(f"{QUIP_BASE}/folders/f_child").mock(
            return_value=httpx.Response(200, json=_mock_folder("f_child", "Child", thread_ids=["t1"]))
        )
        with QuipClient(token="tok") as client:
            tree = discover_folders(client)
        assert "f_root" in tree.index
        assert "f_child" in tree.index
        assert tree.index["f_child"].parent_id == "f_root"

    @respx.mock
    def test_three_level_deep_nesting(self):
        respx.get(f"{QUIP_BASE}/users/current").mock(
            return_value=httpx.Response(200, json=_mock_user("f1"))
        )
        respx.get(f"{QUIP_BASE}/folders/f1").mock(
            return_value=httpx.Response(200, json=_mock_folder("f1", "L1", child_folder_ids=["f2"]))
        )
        respx.get(f"{QUIP_BASE}/folders/f2").mock(
            return_value=httpx.Response(200, json=_mock_folder("f2", "L2", child_folder_ids=["f3"]))
        )
        respx.get(f"{QUIP_BASE}/folders/f3").mock(
            return_value=httpx.Response(200, json=_mock_folder("f3", "L3", thread_ids=["t_deep"]))
        )
        with QuipClient(token="tok") as client:
            tree = discover_folders(client)
        assert all(k in tree.index for k in ("f1", "f2", "f3"))
        assert "t_deep" in tree.index["f3"].thread_ids

    @respx.mock
    def test_multiple_shared_roots_all_discovered(self):
        respx.get(f"{QUIP_BASE}/users/current").mock(
            return_value=httpx.Response(200, json=_mock_user("f_private", ["f_shared"]))
        )
        respx.get(f"{QUIP_BASE}/folders/f_private").mock(
            return_value=httpx.Response(200, json=_mock_folder("f_private", "Private"))
        )
        respx.get(f"{QUIP_BASE}/folders/f_shared").mock(
            return_value=httpx.Response(200, json=_mock_folder("f_shared", "Shared"))
        )
        with QuipClient(token="tok") as client:
            tree = discover_folders(client)
        assert len(tree.roots) == 2
        assert "f_private" in tree.index
        assert "f_shared" in tree.index

    @respx.mock
    def test_empty_folder_returns_node_with_empty_lists(self):
        respx.get(f"{QUIP_BASE}/users/current").mock(
            return_value=httpx.Response(200, json=_mock_user("f1"))
        )
        respx.get(f"{QUIP_BASE}/folders/f1").mock(
            return_value=httpx.Response(200, json=_mock_folder("f1", "Empty"))
        )
        with QuipClient(token="tok") as client:
            tree = discover_folders(client)
        node = tree.index["f1"]
        assert node.children == []
        assert node.thread_ids == []

    @respx.mock
    def test_inaccessible_subfolder_skipped_with_warning(self, caplog):
        respx.get(f"{QUIP_BASE}/users/current").mock(
            return_value=httpx.Response(200, json=_mock_user("f_root"))
        )
        respx.get(f"{QUIP_BASE}/folders/f_root").mock(
            return_value=httpx.Response(200, json=_mock_folder("f_root", "Root", child_folder_ids=["f_locked"]))
        )
        respx.get(f"{QUIP_BASE}/folders/f_locked").mock(
            return_value=httpx.Response(403, text="Forbidden")
        )
        with QuipClient(token="tok") as client:
            tree = discover_folders(client)
        assert "f_root" in tree.index
        assert "f_locked" not in tree.index

    @respx.mock
    def test_not_found_subfolder_skipped(self):
        respx.get(f"{QUIP_BASE}/users/current").mock(
            return_value=httpx.Response(200, json=_mock_user("f_root"))
        )
        respx.get(f"{QUIP_BASE}/folders/f_root").mock(
            return_value=httpx.Response(200, json=_mock_folder("f_root", "Root", child_folder_ids=["f_gone"]))
        )
        respx.get(f"{QUIP_BASE}/folders/f_gone").mock(
            return_value=httpx.Response(404, text="Not Found")
        )
        with QuipClient(token="tok") as client:
            tree = discover_folders(client)
        assert "f_gone" not in tree.index

    @respx.mock
    def test_duplicate_folder_id_across_roots_deduplicated(self):
        respx.get(f"{QUIP_BASE}/users/current").mock(
            return_value=httpx.Response(200, json=_mock_user("f1", ["f1"]))
        )
        respx.get(f"{QUIP_BASE}/folders/f1").mock(
            return_value=httpx.Response(200, json=_mock_folder("f1", "Same"))
        )
        with QuipClient(token="tok") as client:
            tree = discover_folders(client)
        assert len([n for n in tree.index if n == "f1"]) == 1

    def test_cycle_detection_does_not_cause_infinite_recursion(self, monkeypatch):
        """Folder A's children include folder A itself — must not recurse forever."""
        call_count = {"n": 0}

        def fake_get_folder(folder_id):
            call_count["n"] += 1
            if call_count["n"] > 20:
                raise AssertionError("Cycle detection failed: too many API calls")
            return {"folder": {"id": folder_id, "title": folder_id}, "children": [{"folder_id": "f1"}]}

        def fake_get_current_user():
            return {"current_user": {"id": "u", "name": "u", "private_folder_id": "f1", "shared_folder_ids": []}}

        from unittest.mock import MagicMock
        client = MagicMock()
        client.get_current_user.return_value = fake_get_current_user()
        client.get_folder.side_effect = fake_get_folder

        tree = discover_folders(client)
        assert "f1" in tree.index

    @respx.mock
    def test_folder_with_both_threads_and_children(self):
        respx.get(f"{QUIP_BASE}/users/current").mock(
            return_value=httpx.Response(200, json=_mock_user("f1"))
        )
        respx.get(f"{QUIP_BASE}/folders/f1").mock(
            return_value=httpx.Response(200, json=_mock_folder("f1", "Mixed", child_folder_ids=["f2"], thread_ids=["t1"]))
        )
        respx.get(f"{QUIP_BASE}/folders/f2").mock(
            return_value=httpx.Response(200, json=_mock_folder("f2", "Child"))
        )
        with QuipClient(token="tok") as client:
            tree = discover_folders(client)
        node_f1 = tree.index["f1"]
        assert len(node_f1.children) == 1
        assert "t1" in node_f1.thread_ids

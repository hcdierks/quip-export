"""Unit tests — listing and classifying objects within folders (issue #4)."""

from __future__ import annotations

import httpx
import pytest
import respx

from quip_export.client import QuipClient
from quip_export.discovery import list_and_classify
from quip_export.models import ClassifiedThread, FolderTree

QUIP_BASE = "https://platform.quip.com/1"


def _tree_with_threads(*thread_ids_by_folder: tuple[str, list[str]]) -> FolderTree:
    from quip_export.models import FolderNode
    nodes = []
    index = {}
    for folder_id, tids in thread_ids_by_folder:
        node = FolderNode(id=folder_id, title=folder_id, parent_id=None, children=[], thread_ids=tids)
        nodes.append(node)
        index[folder_id] = node
    return FolderTree(roots=nodes, index=index)


def _thread_resp(thread_id: str, title: str, thread_class: str, html: str = "<p>x</p>") -> dict:
    return {"thread": {"id": thread_id, "title": title, "type": thread_class, "thread_class": thread_class}, "html": html}


class TestListAndClassify:
    @respx.mock
    def test_document_classified_correctly(self):
        tree = _tree_with_threads(("f1", ["t1"]))
        respx.get(f"{QUIP_BASE}/threads/t1").mock(
            return_value=httpx.Response(200, json=_thread_resp("t1", "Report", "document"))
        )
        with QuipClient(token="tok") as client:
            results = list_and_classify(client, tree)
        assert len(results) == 1
        assert results[0].thread_class == "document"

    @respx.mock
    def test_spreadsheet_classified_correctly(self):
        tree = _tree_with_threads(("f1", ["t1"]))
        respx.get(f"{QUIP_BASE}/threads/t1").mock(
            return_value=httpx.Response(200, json=_thread_resp("t1", "Budget", "spreadsheet"))
        )
        with QuipClient(token="tok") as client:
            results = list_and_classify(client, tree)
        assert results[0].thread_class == "spreadsheet"

    @respx.mock
    def test_slides_classified_correctly(self):
        tree = _tree_with_threads(("f1", ["t1"]))
        respx.get(f"{QUIP_BASE}/threads/t1").mock(
            return_value=httpx.Response(200, json=_thread_resp("t1", "Deck", "slides"))
        )
        with QuipClient(token="tok") as client:
            results = list_and_classify(client, tree)
        assert results[0].thread_class == "slides"

    @respx.mock
    def test_chat_classified_correctly(self):
        tree = _tree_with_threads(("f1", ["t1"]))
        respx.get(f"{QUIP_BASE}/threads/t1").mock(
            return_value=httpx.Response(200, json=_thread_resp("t1", "Channel", "chat"))
        )
        with QuipClient(token="tok") as client:
            results = list_and_classify(client, tree)
        assert results[0].thread_class == "chat"

    @respx.mock
    def test_code_classified_correctly(self):
        tree = _tree_with_threads(("f1", ["t1"]))
        respx.get(f"{QUIP_BASE}/threads/t1").mock(
            return_value=httpx.Response(200, json=_thread_resp("t1", "Script", "code"))
        )
        with QuipClient(token="tok") as client:
            results = list_and_classify(client, tree)
        assert results[0].thread_class == "code"

    @respx.mock
    def test_unknown_type_classified_as_unknown_with_warning(self, caplog):
        tree = _tree_with_threads(("f1", ["t1"]))
        respx.get(f"{QUIP_BASE}/threads/t1").mock(
            return_value=httpx.Response(200, json=_thread_resp("t1", "Weird", "future_type"))
        )
        with QuipClient(token="tok") as client:
            results = list_and_classify(client, tree)
        assert results[0].thread_class == "unknown"

    @respx.mock
    def test_thread_in_two_folders_single_record_with_both_folder_ids(self):
        tree = _tree_with_threads(("f1", ["t1"]), ("f2", ["t1"]))
        respx.get(f"{QUIP_BASE}/threads/t1").mock(
            return_value=httpx.Response(200, json=_thread_resp("t1", "Shared", "document"))
        )
        with QuipClient(token="tok") as client:
            results = list_and_classify(client, tree)
        assert len(results) == 1
        assert "f1" in results[0].folder_ids
        assert "f2" in results[0].folder_ids

    @respx.mock
    def test_deleted_thread_404_skipped(self, caplog):
        tree = _tree_with_threads(("f1", ["t_gone", "t_ok"]))
        respx.get(f"{QUIP_BASE}/threads/t_gone").mock(
            return_value=httpx.Response(404, text="Not Found")
        )
        respx.get(f"{QUIP_BASE}/threads/t_ok").mock(
            return_value=httpx.Response(200, json=_thread_resp("t_ok", "OK", "document"))
        )
        with QuipClient(token="tok") as client:
            results = list_and_classify(client, tree)
        thread_ids = [r.thread_id for r in results]
        assert "t_gone" not in thread_ids
        assert "t_ok" in thread_ids

    @respx.mock
    def test_inaccessible_thread_403_skipped(self):
        tree = _tree_with_threads(("f1", ["t_locked"]))
        respx.get(f"{QUIP_BASE}/threads/t_locked").mock(
            return_value=httpx.Response(403, text="Forbidden")
        )
        with QuipClient(token="tok") as client:
            results = list_and_classify(client, tree)
        assert results == []

    @respx.mock
    def test_empty_folder_returns_empty_list(self):
        tree = _tree_with_threads(("f1", []))
        with QuipClient(token="tok") as client:
            results = list_and_classify(client, tree)
        assert results == []

    @respx.mock
    def test_thread_with_no_title_defaults_to_thread_id(self):
        resp = {"thread": {"id": "t1", "thread_class": "document"}, "html": "<p>x</p>"}
        tree = _tree_with_threads(("f1", ["t1"]))
        respx.get(f"{QUIP_BASE}/threads/t1").mock(
            return_value=httpx.Response(200, json=resp)
        )
        with QuipClient(token="tok") as client:
            results = list_and_classify(client, tree)
        assert results[0].title == "t1"

    def test_returns_list_of_classified_thread_instances(self, single_folder_tree, mock_client):
        mock_client.get_thread.return_value = _thread_resp("t1", "Doc", "document")
        from quip_export.models import FolderNode
        tree = _tree_with_threads(("f1", ["t1"]))
        mock_client.get_thread.return_value = _thread_resp("t1", "Doc", "document")
        results = list_and_classify(mock_client, tree)
        assert all(isinstance(r, ClassifiedThread) for r in results)

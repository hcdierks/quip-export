"""Unit-test fixtures.

These fixtures import from quip_export.models and related modules.
They will fail with ImportError until those modules are implemented — that
is the expected TDD red state.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from quip_export.models import ClassifiedThread, DuplicateRecord, FolderNode, FolderTree

# ---------------------------------------------------------------------------
# FolderNode / FolderTree builders
# ---------------------------------------------------------------------------

def _node(
    folder_id: str,
    title: str = "",
    parent_id: str | None = None,
    children: list[FolderNode] | None = None,
    thread_ids: list[str] | None = None,
) -> FolderNode:
    return FolderNode(
        id=folder_id,
        title=title or folder_id,
        parent_id=parent_id,
        children=children or [],
        thread_ids=thread_ids or [],
    )


def _tree(*roots: FolderNode) -> FolderTree:
    index: dict[str, FolderNode] = {}

    def _index(node: FolderNode) -> None:
        index[node.id] = node
        for child in node.children:
            _index(child)

    for root in roots:
        _index(root)
    return FolderTree(roots=list(roots), index=index)


@pytest.fixture()
def single_folder_tree() -> FolderTree:
    """One root folder with no children and two threads."""
    root = _node("f1", "Root", thread_ids=["t1", "t2"])
    return _tree(root)


@pytest.fixture()
def two_level_tree() -> FolderTree:
    """Root with one child folder; threads in both."""
    child = _node("f2", "Child", parent_id="f1", thread_ids=["t3"])
    root = _node("f1", "Root", children=[child], thread_ids=["t1", "t2"])
    return _tree(root)


@pytest.fixture()
def deep_tree() -> FolderTree:
    """Three levels: root → finance → q1."""
    q1 = _node("f_q1", "Q1", parent_id="f_finance", thread_ids=["t_q1"])
    finance = _node("f_finance", "Finance", parent_id="f_root", children=[q1], thread_ids=["t_fin"])
    root = _node("f_root", "Root", children=[finance])
    return _tree(root)


@pytest.fixture()
def multi_root_tree() -> FolderTree:
    """Private root and one shared root."""
    private = _node("f_private", "Private Docs", thread_ids=["t1"])
    shared = _node("f_shared", "Shared Workspace", thread_ids=["t2"])
    return _tree(private, shared)


# ---------------------------------------------------------------------------
# ClassifiedThread builders
# ---------------------------------------------------------------------------

def _thread(
    thread_id: str = "t1",
    title: str = "Untitled",
    thread_class: str = "document",
    folder_ids: list[str] | None = None,
) -> ClassifiedThread:
    return ClassifiedThread(
        thread_id=thread_id,
        title=title,
        thread_class=thread_class,
        folder_ids=folder_ids or ["f1"],
    )


@pytest.fixture()
def doc_thread() -> ClassifiedThread:
    return _thread("t_doc", "My Document", "document", ["f1"])


@pytest.fixture()
def sheet_thread() -> ClassifiedThread:
    return _thread("t_sheet", "My Spreadsheet", "spreadsheet", ["f1"])


@pytest.fixture()
def slides_thread() -> ClassifiedThread:
    return _thread("t_slides", "My Presentation", "slides", ["f1"])


@pytest.fixture()
def chat_thread() -> ClassifiedThread:
    return _thread("t_chat", "Team Chat", "chat", ["f1"])


@pytest.fixture()
def code_thread() -> ClassifiedThread:
    return _thread("t_code", "Script", "code", ["f1"])


@pytest.fixture()
def unknown_thread() -> ClassifiedThread:
    return _thread("t_unk", "Unknown Thing", "unknown", ["f1"])


@pytest.fixture()
def multi_folder_thread() -> ClassifiedThread:
    """Thread that lives in two folders."""
    return _thread("t_dup", "Shared Doc", "document", ["f1", "f2"])


@pytest.fixture()
def three_folder_thread() -> ClassifiedThread:
    return _thread("t_tri", "Triple Shared", "document", ["f1", "f2", "f3"])


@pytest.fixture()
def classified_thread_factory():
    return _thread


# ---------------------------------------------------------------------------
# DuplicateRecord builders
# ---------------------------------------------------------------------------

@pytest.fixture()
def duplicate_record_two_paths(tmp_path) -> DuplicateRecord:
    return DuplicateRecord(
        thread_id="t_dup",
        title="Shared Doc",
        paths=[tmp_path / "Folder1" / "Shared Doc.docx", tmp_path / "Folder2" / "Shared Doc.docx"],
    )


@pytest.fixture()
def duplicate_record_four_paths(tmp_path) -> DuplicateRecord:
    return DuplicateRecord(
        thread_id="t_quad",
        title="Quad Doc",
        paths=[
            tmp_path / "A" / "Quad Doc.docx",
            tmp_path / "B" / "Quad Doc.docx",
            tmp_path / "C" / "Quad Doc.docx",
            tmp_path / "D" / "Quad Doc.docx",
        ],
    )


@pytest.fixture()
def duplicate_record_factory():
    def _make(thread_id: str, title: str, paths: list[Path]) -> DuplicateRecord:
        return DuplicateRecord(thread_id=thread_id, title=title, paths=paths)
    return _make


# ---------------------------------------------------------------------------
# Folder-ID → Path map
# ---------------------------------------------------------------------------

@pytest.fixture()
def folder_path_map(tmp_path) -> dict[str, Path]:
    dirs = {
        "f1": tmp_path / "Root",
        "f2": tmp_path / "Root" / "Child",
        "f3": tmp_path / "Root" / "Other",
    }
    for d in dirs.values():
        d.mkdir(parents=True, exist_ok=True)
    return dirs


# ---------------------------------------------------------------------------
# Mock QuipClient
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_client() -> MagicMock:
    return MagicMock()

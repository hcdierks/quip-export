"""Discover the folder hierarchy and classify thread objects."""

from __future__ import annotations

import logging
from typing import Any

from quip_export.client import QuipAPIError
from quip_export.models import ClassifiedThread, FolderNode, FolderTree

log = logging.getLogger(__name__)

_KNOWN_CLASSES = {"document", "spreadsheet", "slides", "chat", "code"}


def discover_folders(client: Any) -> FolderTree:
    """Walk the full folder tree reachable by the authenticated user."""
    cu = client.get_current_user()
    root_ids: list[str] = (
        [cu["private_folder_id"]]
        + list(cu.get("shared_folder_ids", []))
        + list(cu.get("group_folder_ids", []))
    )

    index: dict[str, FolderNode] = {}
    roots: list[FolderNode] = []

    def _fetch(folder_id: str, parent_id: str | None) -> FolderNode | None:
        if folder_id in index:
            return index[folder_id]
        try:
            data = client.get_folder(folder_id)
        except QuipAPIError as exc:
            log.warning("Skipping inaccessible folder %s: %s", folder_id, exc)
            return None

        children_data = data.get("children", [])
        thread_ids = [c["thread_id"] for c in children_data if "thread_id" in c]
        child_folder_ids = [c["folder_id"] for c in children_data if "folder_id" in c]

        node = FolderNode(
            id=folder_id,
            title=data["folder"]["title"],
            parent_id=parent_id,
            children=[],
            thread_ids=thread_ids,
        )
        index[folder_id] = node

        for child_id in child_folder_ids:
            child = _fetch(child_id, folder_id)
            if child is not None:
                node.children.append(child)

        return node

    seen: set[str] = set()
    for root_id in root_ids:
        if root_id in seen:
            continue
        seen.add(root_id)
        node = _fetch(root_id, None)
        if node is not None:
            roots.append(node)

    return FolderTree(roots=roots, index=index)


def list_and_classify(client: Any, tree: FolderTree) -> list[ClassifiedThread]:
    """Fetch every thread in the tree and return classified records."""
    thread_to_folders: dict[str, list[str]] = {}
    for folder_id, node in tree.index.items():
        for tid in node.thread_ids:
            thread_to_folders.setdefault(tid, []).append(folder_id)

    results: list[ClassifiedThread] = []
    for thread_id, folder_ids in thread_to_folders.items():
        try:
            data = client.get_thread(thread_id)
        except QuipAPIError as exc:
            log.warning("Skipping inaccessible thread %s: %s", thread_id, exc)
            continue

        thread = data["thread"]
        raw_class = thread.get("thread_class") or thread.get("type", "")
        if raw_class not in _KNOWN_CLASSES:
            log.warning("Unknown thread class %r for %s", raw_class, thread_id)
            raw_class = "unknown"

        title = thread.get("title") or thread_id
        results.append(
            ClassifiedThread(
                thread_id=thread_id,
                title=title,
                thread_class=raw_class,
                folder_ids=folder_ids,
            )
        )

    return results

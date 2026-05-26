"""Filesystem utilities: name sanitisation and directory structure creation."""

from __future__ import annotations

import re
from pathlib import Path

from quip_export.models import FolderNode, FolderTree

_ILLEGAL = re.compile(r'[/\\:*?"<>|]')
_MULTI_SPACE = re.compile(r" {2,}")
_MAX_LEN = 200


def sanitise_name(title: str, folder_id: str) -> str:
    """Return a filesystem-safe version of *title*, falling back to *folder_id*."""
    name = _ILLEGAL.sub(" ", title)
    name = _MULTI_SPACE.sub(" ", name).strip()
    name = name[:_MAX_LEN]
    return name if name else folder_id


def create_directory_structure(tree: FolderTree, base_dir: Path) -> dict[str, Path]:
    """Create one directory per FolderNode under *base_dir* and return a mapping."""
    mapping: dict[str, Path] = {}

    def _create(node: FolderNode, parent: Path, sibling_names: set[str]) -> None:
        name = sanitise_name(node.title, node.id)
        if name in sibling_names:
            name = f"{name} ({node.id})"
        sibling_names.add(name)
        path = parent / name
        path.mkdir(parents=True, exist_ok=True)
        mapping[node.id] = path
        child_names: set[str] = set()
        for child in node.children:
            _create(child, path, child_names)

    root_names: set[str] = set()
    for root in tree.roots:
        _create(root, base_dir, root_names)

    return mapping

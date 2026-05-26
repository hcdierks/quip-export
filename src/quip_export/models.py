"""Domain model dataclasses for quip-export."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class FolderNode:
    id: str
    title: str
    parent_id: str | None
    children: list[FolderNode]
    thread_ids: list[str]


@dataclass
class FolderTree:
    roots: list[FolderNode]
    index: dict[str, FolderNode]


@dataclass
class ClassifiedThread:
    thread_id: str
    title: str
    thread_class: str
    folder_ids: list[str]


@dataclass
class DuplicateRecord:
    thread_id: str
    title: str
    paths: list[Path]

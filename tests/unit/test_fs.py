"""Unit tests — local filesystem directory creation (issue #3)."""

from __future__ import annotations

import stat
from pathlib import Path

import pytest

from quip_export.fs import create_directory_structure, sanitise_name


class TestSanitiseName:
    def test_forward_slash_replaced(self):
        assert "/" not in sanitise_name("Q1/Results", "f1")

    def test_backslash_replaced(self):
        assert "\\" not in sanitise_name("Win\\Path", "f1")

    def test_colon_replaced(self):
        assert ":" not in sanitise_name("Title: Subtitle", "f1")

    def test_asterisk_replaced(self):
        assert "*" not in sanitise_name("Wild*card", "f1")

    def test_question_mark_replaced(self):
        assert "?" not in sanitise_name("What?", "f1")

    def test_double_quote_replaced(self):
        assert '"' not in sanitise_name('Say "hello"', "f1")

    def test_angle_brackets_replaced(self):
        name = sanitise_name("<tag>", "f1")
        assert "<" not in name and ">" not in name

    def test_pipe_replaced(self):
        assert "|" not in sanitise_name("A|B", "f1")

    def test_trailing_whitespace_stripped(self):
        assert sanitise_name("Name   ", "f1") == sanitise_name("Name", "f1")

    def test_consecutive_whitespace_collapsed(self):
        result = sanitise_name("Too  Many   Spaces", "f1")
        assert "  " not in result

    def test_name_truncated_to_200_chars(self):
        long_name = "A" * 300
        assert len(sanitise_name(long_name, "f1")) <= 200

    def test_empty_after_sanitisation_falls_back_to_folder_id(self):
        result = sanitise_name("////", "f_abc")
        assert result == "f_abc"

    def test_normal_name_unchanged(self):
        assert sanitise_name("Finance Reports", "f1") == "Finance Reports"

    def test_special_chars_in_middle_preserved(self):
        result = sanitise_name("Q1 & Q2 Results", "f1")
        assert "Q1" in result and "Q2" in result


class TestCreateDirectoryStructure:
    def test_single_root_created(self, single_folder_tree, tmp_path):
        mapping = create_directory_structure(single_folder_tree, tmp_path)
        assert "f1" in mapping
        assert mapping["f1"].exists()

    def test_nested_hierarchy_created(self, two_level_tree, tmp_path):
        mapping = create_directory_structure(two_level_tree, tmp_path)
        assert "f1" in mapping
        assert "f2" in mapping
        assert mapping["f2"].exists()
        assert mapping["f2"].parent == mapping["f1"]

    def test_deeply_nested_all_dirs_created(self, deep_tree, tmp_path):
        mapping = create_directory_structure(deep_tree, tmp_path)
        for folder_id in ("f_root", "f_finance", "f_q1"):
            assert folder_id in mapping
            assert mapping[folder_id].exists()

    def test_returns_mapping_for_every_folder(self, two_level_tree, tmp_path):
        mapping = create_directory_structure(two_level_tree, tmp_path)
        assert len(mapping) == len(two_level_tree.index)

    def test_idempotent_on_existing_dirs(self, single_folder_tree, tmp_path):
        create_directory_structure(single_folder_tree, tmp_path)
        mapping2 = create_directory_structure(single_folder_tree, tmp_path)
        assert mapping2["f1"].exists()

    def test_collision_resolved_with_suffix(self, tmp_path):
        from quip_export.models import FolderNode, FolderTree
        # Two sibling folders that sanitise to the same name
        child_a = FolderNode(id="fa", title="Reports", parent_id="root", children=[], thread_ids=[])
        child_b = FolderNode(id="fb", title="Reports", parent_id="root", children=[], thread_ids=[])
        root = FolderNode(
            id="root", title="Root", parent_id=None, children=[child_a, child_b], thread_ids=[]
        )
        tree = FolderTree(roots=[root], index={"root": root, "fa": child_a, "fb": child_b})
        mapping = create_directory_structure(tree, tmp_path)
        paths = {mapping["fa"].name, mapping["fb"].name}
        assert len(paths) == 2

    def test_read_only_base_raises_permission_error(self, single_folder_tree, tmp_path):
        ro = tmp_path / "readonly"
        ro.mkdir()
        ro.chmod(stat.S_IREAD | stat.S_IEXEC)
        try:
            with pytest.raises(PermissionError):
                create_directory_structure(single_folder_tree, ro)
        finally:
            ro.chmod(stat.S_IRWXU)

    def test_all_values_are_path_instances(self, two_level_tree, tmp_path):
        mapping = create_directory_structure(two_level_tree, tmp_path)
        assert all(isinstance(p, Path) for p in mapping.values())

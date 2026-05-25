"""Tests for the export orchestration logic."""

import pytest
import respx
import httpx
from pathlib import Path
from unittest.mock import MagicMock

from quip_export.client import QuipClient
from quip_export.exporter import OutputFormat, export_thread


@respx.mock
def test_export_thread_markdown(tmp_path, sample_thread):
    respx.get("https://platform.quip.com/1/threads/abc123").mock(
        return_value=httpx.Response(200, json=sample_thread)
    )
    with QuipClient(token="fake-token") as client:
        paths = export_thread(client, "abc123", tmp_path, [OutputFormat.markdown])

    assert len(paths) == 1
    assert paths[0].suffix == ".md"
    assert paths[0].exists()


@respx.mock
def test_export_thread_multiple_formats(tmp_path, sample_thread):
    respx.get("https://platform.quip.com/1/threads/abc123").mock(
        return_value=httpx.Response(200, json=sample_thread)
    )
    with QuipClient(token="fake-token") as client:
        paths = export_thread(
            client, "abc123", tmp_path, [OutputFormat.markdown, OutputFormat.docx]
        )

    suffixes = {p.suffix for p in paths}
    assert ".md" in suffixes
    assert ".docx" in suffixes


@respx.mock
def test_export_thread_sanitizes_filename(tmp_path, sample_thread):
    thread = {**sample_thread, "thread": {**sample_thread["thread"], "title": "My Doc: Special/Chars?"}}
    respx.get("https://platform.quip.com/1/threads/abc123").mock(
        return_value=httpx.Response(200, json=thread)
    )
    with QuipClient(token="fake-token") as client:
        paths = export_thread(client, "abc123", tmp_path, [OutputFormat.markdown])

    assert paths[0].exists()
    assert "/" not in paths[0].name

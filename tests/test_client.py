"""Tests for the Quip API client."""

import pytest
import respx
import httpx

from quip_export.client import QuipAuthError, QuipAPIError, QuipClient


def test_raises_without_token(monkeypatch):
    monkeypatch.delenv("QUIP_TOKEN", raising=False)
    with pytest.raises(QuipAuthError):
        QuipClient()


def test_raises_with_empty_token(monkeypatch):
    monkeypatch.delenv("QUIP_TOKEN", raising=False)
    with pytest.raises(QuipAuthError):
        QuipClient(token="")


@respx.mock
def test_get_thread_success(sample_thread):
    respx.get("https://platform.quip.com/1/threads/abc123").mock(
        return_value=httpx.Response(200, json=sample_thread)
    )
    with QuipClient(token="fake-token") as client:
        result = client.get_thread("abc123")
    assert result["thread"]["id"] == "abc123"


@respx.mock
def test_get_thread_raises_on_error():
    respx.get("https://platform.quip.com/1/threads/bad").mock(
        return_value=httpx.Response(403, text="Forbidden")
    )
    with QuipClient(token="fake-token") as client:
        with pytest.raises(QuipAPIError) as exc_info:
            client.get_thread("bad")
    assert exc_info.value.status_code == 403

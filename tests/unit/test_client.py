"""Unit tests — Quip API client (issue #1, enhanced from initial scaffold)."""

from __future__ import annotations

import httpx
import pytest
import respx

from quip_export.client import QuipAPIError, QuipAuthError, QuipClient

QUIP_BASE = "https://platform.quip.com/1"


class TestClientConstruction:
    def test_raises_without_token_and_no_env(self, monkeypatch):
        monkeypatch.delenv("QUIP_TOKEN", raising=False)
        with pytest.raises(QuipAuthError):
            QuipClient()

    def test_raises_with_empty_token(self, monkeypatch):
        monkeypatch.delenv("QUIP_TOKEN", raising=False)
        with pytest.raises(QuipAuthError):
            QuipClient(token="")

    def test_uses_env_token_when_no_flag(self, monkeypatch):
        monkeypatch.setenv("QUIP_TOKEN", "env_token")
        client = QuipClient()
        assert client is not None
        client.close()

    def test_flag_token_used(self):
        client = QuipClient(token="explicit_token")
        assert client is not None
        client.close()

    def test_context_manager_closes_on_exit(self):
        with QuipClient(token="tok") as client:
            assert client is not None


class TestGetThread:
    @respx.mock
    def test_success_returns_parsed_json(self, sample_thread):
        respx.get(f"{QUIP_BASE}/threads/abc123").mock(
            return_value=httpx.Response(200, json=sample_thread)
        )
        with QuipClient(token="tok") as client:
            result = client.get_thread("abc123")
        assert result["thread"]["id"] == sample_thread["thread"]["id"]

    @respx.mock
    def test_403_raises_api_error(self):
        respx.get(f"{QUIP_BASE}/threads/bad").mock(
            return_value=httpx.Response(403, text="Forbidden")
        )
        with QuipClient(token="tok") as client:
            with pytest.raises(QuipAPIError) as exc_info:
                client.get_thread("bad")
        assert exc_info.value.status_code == 403

    @respx.mock
    def test_404_raises_api_error(self):
        respx.get(f"{QUIP_BASE}/threads/gone").mock(
            return_value=httpx.Response(404, text="Not Found")
        )
        with QuipClient(token="tok") as client:
            with pytest.raises(QuipAPIError) as exc_info:
                client.get_thread("gone")
        assert exc_info.value.status_code == 404


class TestGetFolder:
    @respx.mock
    def test_success_returns_folder_data(self, folder_response_factory):
        payload = folder_response_factory("f1", "My Folder", thread_ids=["t1"])
        respx.get(f"{QUIP_BASE}/folders/f1").mock(
            return_value=httpx.Response(200, json=payload)
        )
        with QuipClient(token="tok") as client:
            result = client.get_folder("f1")
        assert result["folder"]["id"] == "f1"

    @respx.mock
    def test_403_raises_api_error(self):
        respx.get(f"{QUIP_BASE}/folders/private").mock(
            return_value=httpx.Response(403, text="Forbidden")
        )
        with QuipClient(token="tok") as client:
            with pytest.raises(QuipAPIError) as exc_info:
                client.get_folder("private")
        assert exc_info.value.status_code == 403


class TestGetCurrentUser:
    @respx.mock
    def test_returns_user_with_folder_ids(self, user_response_factory):
        payload = user_response_factory("u1", "f_private", ["f_shared"])
        respx.get(f"{QUIP_BASE}/users/current").mock(
            return_value=httpx.Response(200, json=payload)
        )
        with QuipClient(token="tok") as client:
            result = client.get_current_user()
        assert result["current_user"]["private_folder_id"] == "f_private"
        assert "f_shared" in result["current_user"]["shared_folder_ids"]

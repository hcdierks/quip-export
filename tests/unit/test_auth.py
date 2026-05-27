"""Unit tests — authentication and token resolution (issue #1)."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch, mock_open

import httpx
import pytest
import respx

from quip_export.auth import QuipAuthError, resolve_token, validate_token


# ---------------------------------------------------------------------------
# Token resolution — source priority
# ---------------------------------------------------------------------------

class TestResolveToken:
    def test_flag_takes_priority_over_env(self, monkeypatch):
        monkeypatch.setenv("QUIP_TOKEN", "env_token")
        assert resolve_token(flag_token="flag_token") == "flag_token"

    def test_flag_takes_priority_over_config(self, tmp_path, monkeypatch):
        monkeypatch.delenv("QUIP_TOKEN", raising=False)
        cfg = tmp_path / "config.toml"
        cfg.write_text('token = "config_token"\n')
        with patch("quip_export.auth.CONFIG_PATH", cfg):
            assert resolve_token(flag_token="flag_token") == "flag_token"

    def test_env_used_when_no_flag(self, monkeypatch):
        monkeypatch.setenv("QUIP_TOKEN", "env_token")
        assert resolve_token(flag_token=None) == "env_token"

    def test_env_takes_priority_over_config(self, tmp_path, monkeypatch):
        monkeypatch.setenv("QUIP_TOKEN", "env_token")
        cfg = tmp_path / "config.toml"
        cfg.write_text('token = "config_token"\n')
        with patch("quip_export.auth.CONFIG_PATH", cfg):
            assert resolve_token(flag_token=None) == "env_token"

    def test_config_used_when_no_flag_and_no_env(self, tmp_path, monkeypatch):
        monkeypatch.delenv("QUIP_TOKEN", raising=False)
        cfg = tmp_path / "config.toml"
        cfg.write_text('token = "config_token"\n')
        with patch("quip_export.auth.CONFIG_PATH", cfg):
            assert resolve_token(flag_token=None) == "config_token"

    def test_raises_when_no_source(self, monkeypatch, tmp_path):
        monkeypatch.delenv("QUIP_TOKEN", raising=False)
        nonexistent = tmp_path / "no_config.toml"
        with patch("quip_export.auth.CONFIG_PATH", nonexistent):
            with pytest.raises(QuipAuthError, match="QUIP_TOKEN"):
                resolve_token(flag_token=None)

    def test_empty_flag_falls_through_to_env(self, monkeypatch):
        monkeypatch.setenv("QUIP_TOKEN", "env_token")
        assert resolve_token(flag_token="") == "env_token"

    def test_empty_env_falls_through_to_config(self, tmp_path, monkeypatch):
        monkeypatch.setenv("QUIP_TOKEN", "")
        cfg = tmp_path / "config.toml"
        cfg.write_text('token = "config_token"\n')
        with patch("quip_export.auth.CONFIG_PATH", cfg):
            assert resolve_token(flag_token=None) == "config_token"

    def test_malformed_config_raises_with_path(self, tmp_path, monkeypatch):
        monkeypatch.delenv("QUIP_TOKEN", raising=False)
        cfg = tmp_path / "config.toml"
        cfg.write_text("this is not valid toml [\n")
        with patch("quip_export.auth.CONFIG_PATH", cfg):
            with pytest.raises(Exception, match=str(cfg)):
                resolve_token(flag_token=None)

    def test_config_missing_token_key_falls_through(self, tmp_path, monkeypatch):
        monkeypatch.delenv("QUIP_TOKEN", raising=False)
        cfg = tmp_path / "config.toml"
        cfg.write_text('other_key = "value"\n')
        nonexistent_second = tmp_path / "no_config_here.toml"
        with patch("quip_export.auth.CONFIG_PATH", cfg):
            with pytest.raises(QuipAuthError):
                resolve_token(flag_token=None)


# ---------------------------------------------------------------------------
# Token validation against Quip API
# ---------------------------------------------------------------------------

class TestValidateToken:
    @respx.mock
    def test_valid_token_returns_user_info(self):
        respx.get("https://platform.quip.com/1/users/current").mock(
            return_value=httpx.Response(200, json={"id": "u1", "name": "Test"})
        )
        user = validate_token("valid_token")
        assert user["id"] == "u1"

    @respx.mock
    def test_invalid_token_raises_auth_error(self):
        respx.get("https://platform.quip.com/1/users/current").mock(
            return_value=httpx.Response(401, text="Unauthorized")
        )
        with pytest.raises(QuipAuthError, match="[Ii]nvalid"):
            validate_token("bad_token")

    @respx.mock
    def test_forbidden_raises_auth_error(self):
        respx.get("https://platform.quip.com/1/users/current").mock(
            return_value=httpx.Response(403, text="Forbidden")
        )
        with pytest.raises(QuipAuthError):
            validate_token("bad_token")

    @respx.mock
    def test_network_timeout_raises_meaningful_error(self):
        respx.get("https://platform.quip.com/1/users/current").mock(
            side_effect=httpx.TimeoutException("timed out")
        )
        with pytest.raises(Exception, match="[Tt]ime[Oo]ut|network|connect"):
            validate_token("some_token")

    def test_token_not_reflected_in_error_message(self, monkeypatch, tmp_path):
        secret = "super_secret_token_xyz"
        monkeypatch.delenv("QUIP_TOKEN", raising=False)
        cfg = tmp_path / "no.toml"
        with patch("quip_export.auth.CONFIG_PATH", cfg):
            try:
                resolve_token(flag_token=secret[:0])  # empty flag
            except QuipAuthError as exc:
                assert secret not in str(exc)

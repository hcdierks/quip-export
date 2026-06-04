"""Unit tests — authentication and token resolution (issue #1)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from quip_export.auth import QuipAuthError, resolve_token

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
        with patch("quip_export.auth.CONFIG_PATH", nonexistent):  # noqa: SIM117
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
        with patch("quip_export.auth.CONFIG_PATH", cfg), pytest.raises(Exception, match=str(cfg)):
            resolve_token(flag_token=None)

    def test_config_missing_token_key_falls_through(self, tmp_path, monkeypatch):
        monkeypatch.delenv("QUIP_TOKEN", raising=False)
        cfg = tmp_path / "config.toml"
        cfg.write_text('other_key = "value"\n')
        tmp_path / "no_config_here.toml"
        with patch("quip_export.auth.CONFIG_PATH", cfg), pytest.raises(QuipAuthError):
            resolve_token(flag_token=None)

"""Regression tests for the audit fixes (redirects, TLS fallback, URL
defaults, bad ints, profile names)."""

from unittest.mock import MagicMock, patch

import pytest
import requests

from core.advanced_flags import validate_advanced_state
from core.album_choice import AlbumFetchError, fetch_album_names
from core.config_manager import load_config
from core.network import normalize_server_url
from core.network import test_immich_connection as run_conn_test


def _resp(status, payload=None):
    r = MagicMock(status_code=status, ok=200 <= status < 300)
    r.json.return_value = payload or []
    return r


def test_connection_test_does_not_follow_redirect():
    with patch("requests.get", return_value=_resp(302)) as get:
        res = run_conn_test("https://photos.example.com", "k")
    assert get.call_args.kwargs["allow_redirects"] is False
    assert not res.ok and "redirect" in res.message


def test_album_fetch_does_not_follow_redirect():
    with patch("requests.get", return_value=_resp(301)) as get:
        with pytest.raises(AlbumFetchError, match="redirect"):
            fetch_album_names("https://photos.example.com", "k")
    assert all(c.kwargs["allow_redirects"] is False for c in get.call_args_list)


def test_album_fetch_never_falls_back_to_http_after_ssl_error():
    with patch("requests.get", side_effect=requests.exceptions.SSLError) as get:
        with pytest.raises(AlbumFetchError, match="secure"):
            fetch_album_names("http://photos.example.com", "k")
    urls = [c.args[0] for c in get.call_args_list]
    assert urls and all(u.startswith("https://") for u in urls)


def test_album_fetch_falls_back_to_explicit_http_on_refused():
    side = [requests.exceptions.ConnectionError, _resp(200, [{"albumName": "B"}])]
    with patch("requests.get", side_effect=side) as get:
        assert fetch_album_names("http://photos.example.com", "k") == ["B"]
    assert get.call_args.args[0].startswith("http://photos.example.com")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("photos.example.com", "https://photos.example.com"),
        ("photos.example.com:2283/", "https://photos.example.com:2283"),
        ("http://photos.example.com", "http://photos.example.com"),
        ("localhost:2283", "http://localhost:2283"),
        ("nas.local:2283", "http://nas.local:2283"),
        ("192.168.1.10:2283", "http://192.168.1.10:2283"),
        ("127.0.0.1", "http://127.0.0.1"),
        ("immich:2283", "http://immich:2283"),
    ],
)
def test_normalize_server_url_scheme_defaults(raw, expected):
    assert normalize_server_url(raw) == expected


def test_bad_client_timeout_falls_back_to_60(tmp_path, monkeypatch):
    cfg = tmp_path / "config.toml"
    monkeypatch.setenv("IMMICH_GO_GUI_CONFIG", str(cfg))
    cfg.write_text('schema_version = 3\n[server]\nclient_timeout_minutes = "abc"\n')
    assert load_config(cfg).client_timeout_minutes == 60


@pytest.mark.parametrize(
    ("value", "msg"),
    [("abc", "whole number"), (0, "at least 1"), (99, "at most 20")],
)
def test_bad_int_advanced_flag_is_a_user_error(value, msg):
    state = {"concurrent-tasks": {"enabled": True, "value": value}}
    res = validate_advanced_state("upload-folder", state)
    assert any(msg in e for e in res.errors)
    ok = validate_advanced_state(
        "upload-folder", {"concurrent-tasks": {"enabled": True, "value": 4}}
    )
    assert not ok.errors


def test_bad_profile_name_in_index_is_rejected(tmp_path, monkeypatch):
    from core import profile_manager as pm

    monkeypatch.setenv("IMMICH_GO_GUI_CONFIG", str(tmp_path / "config.toml"))
    pm.clear_profiles_cache()
    pm.ensure_default_profile()
    pm.global_profiles_path().write_text(
        'schema_version = 1\nactive_profile = "../../evil"\n'
        '[[profiles]]\nname = "default"\n[[profiles]]\nname = "../../evil"\n'
    )
    pm.clear_profiles_cache()
    assert pm.active_profile_name() == "default"
    assert [p.name for p in pm.list_profiles()] == ["default"]
    assert pm.profile_dir("../../evil") == pm.profiles_root() / "default"
    pm.clear_profiles_cache()

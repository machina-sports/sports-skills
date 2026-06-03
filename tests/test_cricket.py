"""Tests for the cricket module — ESPN live backend and Cricsheet historical backend."""

import io
import json
import os
import time
import zipfile

import pytest

from sports_skills.cricket import _cricsheet

# ── get_competitions ────────────────────────────────────────


class TestGetCompetitions:
    def test_returns_known_codes_with_attribution(self):
        result = _cricsheet.get_competitions({})
        codes = {c["code"] for c in result["competitions"]}
        assert "ipl" in codes
        assert "tests" in codes
        assert "wbb" in codes
        assert result["count"] == len(result["competitions"])
        assert "cricsheet.org" in result["attribution"]

    def test_every_competition_has_name(self):
        result = _cricsheet.get_competitions({})
        for c in result["competitions"]:
            assert c["code"]
            assert c["name"]


# ── cache layer ─────────────────────────────────────────────


class TestFetchFile:
    def test_downloads_when_missing(self, tmp_path, monkeypatch):
        monkeypatch.setattr(_cricsheet, "_cache_dir", lambda: str(tmp_path))
        calls = []

        def fake_download(url, dest):
            calls.append(url)
            with open(dest, "wb") as f:
                f.write(b"payload")

        monkeypatch.setattr(_cricsheet, "_download", fake_download)
        path, stale, err = _cricsheet._fetch_file("http://x/file.zip", "file.zip", ttl=60)
        assert err is None
        assert stale is False
        assert open(path, "rb").read() == b"payload"
        assert calls == ["http://x/file.zip"]

    def test_serves_cached_within_ttl(self, tmp_path, monkeypatch):
        monkeypatch.setattr(_cricsheet, "_cache_dir", lambda: str(tmp_path))
        (tmp_path / "file.zip").write_bytes(b"cached")

        def fail_download(url, dest):
            raise AssertionError("should not download")

        monkeypatch.setattr(_cricsheet, "_download", fail_download)
        path, stale, err = _cricsheet._fetch_file("http://x/file.zip", "file.zip", ttl=3600)
        assert err is None
        assert stale is False
        assert open(path, "rb").read() == b"cached"

    def test_serves_stale_on_download_failure(self, tmp_path, monkeypatch):
        monkeypatch.setattr(_cricsheet, "_cache_dir", lambda: str(tmp_path))
        stale_file = tmp_path / "file.zip"
        stale_file.write_bytes(b"old")
        old = time.time() - 100_000
        os.utime(stale_file, (old, old))

        def fail_download(url, dest):
            raise OSError("network down")

        monkeypatch.setattr(_cricsheet, "_download", fail_download)
        path, stale, err = _cricsheet._fetch_file("http://x/file.zip", "file.zip", ttl=60)
        assert err is None
        assert stale is True
        assert open(path, "rb").read() == b"old"

    def test_error_when_no_cache_and_download_fails(self, tmp_path, monkeypatch):
        monkeypatch.setattr(_cricsheet, "_cache_dir", lambda: str(tmp_path))

        def fail_download(url, dest):
            raise OSError("network down")

        monkeypatch.setattr(_cricsheet, "_download", fail_download)
        path, stale, err = _cricsheet._fetch_file("http://x/file.zip", "file.zip", ttl=60)
        assert path is None
        assert err["error"] is True
        assert "network down" in err["message"]

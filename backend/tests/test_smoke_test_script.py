"""Tests for ``backend/scripts/smoke_test.py``.

We exercise the ``smoke_test()`` helper directly with httpx patched out
via ``unittest.mock``. The argparse entrypoint is exercised through
``main()`` with an explicit ``argv``.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

from scripts.smoke_test import main, smoke_test


def _ok(payload: dict, status_code: int = 200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = payload
    return resp


def _root_ok():
    resp = MagicMock()
    resp.status_code = 200
    return resp


def _root_fail(code: int = 500):
    resp = MagicMock()
    resp.status_code = code
    return resp


class TestHealthyReadyResponse:
    def test_exits_zero_and_prints_pass(self, capsys):
        with patch("scripts.smoke_test.httpx.get") as mock_get:
            mock_get.side_effect = [
                _root_ok(),
                _ok({"kg_status": "ready", "lumber_specs_loaded": 6}),
            ]
            rc = smoke_test("https://example.run.app", allow_disabled=False)
        assert rc == 0
        out = capsys.readouterr().out.strip().splitlines()[-1]
        assert out.startswith("PASS:")
        assert "kg_status=ready" in out


class TestFailureModes:
    def test_root_non_200_exits_one(self, capsys):
        with patch("scripts.smoke_test.httpx.get") as mock_get:
            mock_get.side_effect = [_root_fail(500)]
            rc = smoke_test("https://example.run.app")
        assert rc == 1
        out = capsys.readouterr().out.strip().splitlines()[-1]
        assert out.startswith("FAIL: GET / returned 500")

    def test_kg_endpoint_non_200_exits_one(self, capsys):
        with patch("scripts.smoke_test.httpx.get") as mock_get:
            mock_get.side_effect = [
                _root_ok(),
                _ok({}, status_code=503),
            ]
            rc = smoke_test("https://example.run.app")
        assert rc == 1
        out = capsys.readouterr().out.strip().splitlines()[-1]
        assert out.startswith("FAIL: GET /api/health/kg returned 503")

    def test_kg_status_error_exits_one(self, capsys):
        with patch("scripts.smoke_test.httpx.get") as mock_get:
            mock_get.side_effect = [
                _root_ok(),
                _ok({"kg_status": "error", "lumber_specs_loaded": 0}),
            ]
            rc = smoke_test("https://example.run.app")
        assert rc == 1
        out = capsys.readouterr().out.strip().splitlines()[-1]
        assert out.startswith("FAIL:")
        assert "kg_status=error" in out

    def test_disabled_without_flag_exits_one(self, capsys):
        with patch("scripts.smoke_test.httpx.get") as mock_get:
            mock_get.side_effect = [
                _root_ok(),
                _ok({"kg_status": "disabled", "lumber_specs_loaded": 0}),
            ]
            rc = smoke_test("https://example.run.app", allow_disabled=False)
        assert rc == 1
        out = capsys.readouterr().out.strip().splitlines()[-1]
        assert "kg_status=disabled" in out
        assert out.startswith("FAIL:")

    def test_network_error_exits_one(self, capsys):
        with patch("scripts.smoke_test.httpx.get") as mock_get:
            mock_get.side_effect = httpx.ConnectError("connection refused")
            rc = smoke_test("https://example.run.app")
        assert rc == 1
        out = capsys.readouterr().out.strip().splitlines()[-1]
        assert out.startswith("FAIL: HTTP error:")


class TestAllowDisabledFlag:
    def test_disabled_with_flag_exits_zero(self, capsys):
        with patch("scripts.smoke_test.httpx.get") as mock_get:
            mock_get.side_effect = [
                _root_ok(),
                _ok({"kg_status": "disabled", "lumber_specs_loaded": 0}),
            ]
            rc = smoke_test("https://example.run.app", allow_disabled=True)
        assert rc == 0
        out = capsys.readouterr().out.strip().splitlines()[-1]
        assert out.startswith("PASS:")
        assert "disabled (allowed)" in out


class TestUrlNormalization:
    def test_trailing_slash_stripped(self, capsys):
        with patch("scripts.smoke_test.httpx.get") as mock_get:
            mock_get.side_effect = [
                _root_ok(),
                _ok({"kg_status": "ready", "lumber_specs_loaded": 6}),
            ]
            smoke_test("https://example.run.app/")
        # URLs called should not have double slashes
        calls = [c[0][0] for c in mock_get.call_args_list]
        assert calls[0] == "https://example.run.app/"
        assert calls[1] == "https://example.run.app/api/health/kg"


class TestMainEntrypoint:
    def test_main_parses_url_arg_and_returns_smoke_test_exit_code(self):
        with patch("scripts.smoke_test.smoke_test") as mock_st:
            mock_st.return_value = 0
            rc = main(["--url", "https://example.run.app"])
        assert rc == 0
        mock_st.assert_called_once_with("https://example.run.app", allow_disabled=False)

    def test_main_propagates_allow_disabled_flag(self):
        with patch("scripts.smoke_test.smoke_test") as mock_st:
            mock_st.return_value = 0
            main(["--url", "https://example.run.app", "--allow-disabled"])
        mock_st.assert_called_once_with("https://example.run.app", allow_disabled=True)

    def test_main_requires_url(self):
        with pytest.raises(SystemExit):
            main([])

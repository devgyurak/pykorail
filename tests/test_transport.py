"""전송 계층 — 세션 생성과 CA 번들 해석."""

from __future__ import annotations

import logging
from typing import Any

import pytest

from pykorail import transport
from pykorail.exceptions import TransportError
from pykorail.transport import create_session, resolve_ca_bundle


def _blocking_import(blocked: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """``blocked`` 모듈만 ImportError 를 내도록 만듭니다."""
    real_import = __import__

    def fake_import(name: str, *args: Any):
        return _blow_up() if name == blocked else real_import(name, *args)

    def _blow_up():
        raise ImportError(f"no {blocked}")

    monkeypatch.setattr("builtins.__import__", fake_import)


class TestResolveCaBundle:
    def test_returns_certifi_path_when_present(self) -> None:
        # when
        ca_bundle = resolve_ca_bundle()

        # then
        assert ca_bundle is not None

    def test_returns_none_when_bundle_is_missing(self, monkeypatch, caplog) -> None:
        """PyInstaller 번들에서 certifi 경로가 깨져 있어도 죽지 않아야 합니다."""
        # given
        monkeypatch.setattr("pykorail.transport.Path.is_file", lambda self: False)

        # when
        with caplog.at_level(logging.WARNING):
            ca_bundle = resolve_ca_bundle()

        # then
        assert ca_bundle is None
        assert "CA 번들" in caplog.text

    def test_returns_none_when_certifi_is_absent(self, monkeypatch, caplog) -> None:
        # given
        _blocking_import("certifi", monkeypatch)

        # when
        with caplog.at_level(logging.WARNING):
            ca_bundle = resolve_ca_bundle()

        # then
        assert ca_bundle is None
        assert "certifi" in caplog.text


class TestCreateSession:
    def test_builds_a_curl_cffi_session(self) -> None:
        # when
        session = create_session()

        # then
        assert hasattr(session, "get")
        assert hasattr(session, "post")
        assert hasattr(session, "default_headers")
        assert session.default_headers is False
        session.close()

    def test_applies_headers(self) -> None:
        # when
        session = create_session({"User-Agent": "test-agent"})

        # then
        assert session.headers["User-Agent"] == "test-agent"
        session.close()

    def test_does_not_mutate_the_caller_dict(self) -> None:
        # given
        headers = {"User-Agent": "test-agent"}

        # when
        create_session(headers).close()

        # then
        assert headers == {"User-Agent": "test-agent"}

    def test_falls_back_to_requests(self, monkeypatch, caplog) -> None:
        # given: requests 는 [fallback] 엑스트라라 기본 설치에는 없습니다.
        pytest.importorskip("requests")
        monkeypatch.setattr(transport, "curl_cffi", None)
        monkeypatch.setattr(transport, "CURL_CFFI_IMPORT_ERROR", ImportError("DLL load failed"))

        # when
        with caplog.at_level(logging.WARNING):
            session = create_session({"User-Agent": "test-agent"})

        # then
        assert "requests" in caplog.text, "폴백은 조용히 일어나면 안 됩니다"
        assert session.headers["User-Agent"] == "test-agent"
        session.close()

    def test_raises_when_no_http_library_is_available(self, monkeypatch) -> None:
        # given
        monkeypatch.setattr(transport, "curl_cffi", None)
        _blocking_import("requests", monkeypatch)

        # when & then
        with pytest.raises(TransportError, match="curl_cffi"):
            create_session()

    def test_ca_bundle_is_skipped_when_unresolvable(self, monkeypatch) -> None:
        # given
        monkeypatch.setattr("pykorail.transport.resolve_ca_bundle", lambda: None)

        # when
        session = create_session()

        # then
        assert session is not None
        session.close()

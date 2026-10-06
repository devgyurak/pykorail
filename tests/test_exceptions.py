"""예외 계층과 응답 코드 매핑."""

from __future__ import annotations

import pytest

from pykorail.exceptions import (
    AccessRestrictedError,
    HttpStatusError,
    KorailError,
    NeedToLoginError,
    NetFunnelError,
    NoResultsError,
    PykorailError,
    SoldOutError,
    TransportError,
    error_for_code,
)


class TestHierarchy:
    @pytest.mark.parametrize(
        "error_type",
        [
            KorailError,
            NeedToLoginError,
            NoResultsError,
            SoldOutError,
            NetFunnelError,
            TransportError,
            HttpStatusError,
            AccessRestrictedError,
        ],
    )
    def test_everything_is_a_pykorail_error(self, error_type: type[Exception]) -> None:
        """호출부가 except PykorailError 하나로 라이브러리 실패를 다 잡을 수 있어야 합니다."""
        # when
        is_library_error = issubclass(error_type, PykorailError)

        # then
        assert is_library_error

    def test_netfunnel_is_not_a_korail_error(self) -> None:
        """대기열 게이트는 코레일 응답이 아니므로 형제 타입이어야 합니다."""
        # when
        is_korail_error = issubclass(NetFunnelError, KorailError)

        # then
        assert not is_korail_error

    def test_access_restriction_is_still_an_http_status_error(self) -> None:
        """기존 ``except HttpStatusError`` 호출부가 이용제한도 계속 잡아야 합니다."""
        # when
        is_http_status_error = issubclass(AccessRestrictedError, HttpStatusError)

        # then
        assert is_http_status_error


class TestCodeMapping:
    @pytest.mark.parametrize(
        ("code", "expected"),
        [
            ("P058", NeedToLoginError),
            ("P100", NoResultsError),
            ("WRG000000", NoResultsError),
            ("WRD000061", NoResultsError),
            ("WRT300005", NoResultsError),
            ("IRT010110", SoldOutError),
            ("ERR211161", SoldOutError),
        ],
    )
    def test_known_codes_promote_to_specific_types(self, code: str, expected: type[KorailError]) -> None:
        # when
        error = error_for_code(code, "서버 메시지")

        # then
        assert type(error) is expected
        assert error.code == code

    def test_unknown_code_keeps_server_message(self) -> None:
        # when
        error = error_for_code("ZZZ999", "알 수 없는 오류")

        # then
        assert type(error) is KorailError
        assert error.msg == "알 수 없는 오류"
        assert error.code == "ZZZ999"

    def test_missing_code(self) -> None:
        # when
        error = error_for_code(None, "메시지만 있음")

        # then
        assert type(error) is KorailError
        assert error.code is None

    def test_new_subclass_is_picked_up_without_registration(self) -> None:
        """codes 만 채우면 등록 테이블을 손대지 않아도 매핑돼야 합니다."""

        # given
        class TemporarilyUnavailableError(KorailError):
            codes = frozenset({"TEST9999"})
            default_msg = "잠시 후 다시"

        # when
        error = error_for_code("TEST9999")

        # then
        assert type(error) is TemporarilyUnavailableError
        assert error.msg == "잠시 후 다시"


class TestMessages:
    def test_default_message_applies(self) -> None:
        # when
        error = NoResultsError()

        # then
        assert error.msg == "No Results"

    def test_str_includes_code(self) -> None:
        # given
        error = SoldOutError(code="IRT010110")

        # when
        rendered = str(error)

        # then
        assert rendered == "Sold out (IRT010110)"

    def test_explicit_message_wins(self) -> None:
        # when
        error = NoResultsError("직접 지정")

        # then
        assert error.msg == "직접 지정"

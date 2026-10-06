"""클라이언트 수명주기와 로그인."""

from __future__ import annotations

import base64
from unittest.mock import Mock
from urllib.parse import parse_qsl

import pytest
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad

from pykorail.client import Korail
from pykorail.constants import API_ENDPOINTS
from pykorail.device import DEVICE_PROFILES
from pykorail.exceptions import AccessRestrictedError, LoginFailedError
from tests.conftest import Reply
from tests.dynapath_decoder import decode_token
from tests.payloads import (
    ACCESS_RESTRICTED,
    CIPHER_PAYLOAD,
    LOGIN_FAIL,
    LOGIN_FORM_GOLDEN,
    LOGIN_OK,
    LOGIN_OK_WITHOUT_PROFILE,
    NUMERIC_IDX_CIPHER_PAYLOAD,
    PARTIAL_CIPHER_INFOS,
    UNUSABLE_CIPHER_PAYLOAD,
    cipher_response,
)


class TestConstruction:
    def test_default_android_id_can_be_saved_and_restored(self, make_korail) -> None:
        # given
        first, _ = make_korail({})
        saved_id = first.android_id
        first.close()

        # when
        restored, _ = make_korail({}, android_id=saved_id)
        headers, _ = restored._api.sign(API_ENDPOINTS["login"], include_sid=False)

        # then
        assert restored.device_profile is None
        assert restored.android_id == saved_id
        assert dict(parse_qsl(decode_token(headers["x-dynapath-m-token"])[1]))["di"] == saved_id

    @pytest.mark.parametrize("android_id", ["", "bad", "A" * 16])
    def test_bad_android_id_fails_before_session_creation(self, monkeypatch, android_id: str) -> None:
        # given
        create = Mock()
        monkeypatch.setattr("pykorail.client.create_session", create)

        # when
        with pytest.raises(ValueError, match="android_id"):
            Korail(android_id=android_id)

        # then
        create.assert_not_called()

    def test_conflicting_profile_id_fails_before_session_creation(self, monkeypatch) -> None:
        # given
        create = Mock()
        monkeypatch.setattr("pykorail.client.create_session", create)
        profile = DEVICE_PROFILES[0]
        different = ("0" if profile.android_id[0] != "0" else "1") + profile.android_id[1:]

        # when
        with pytest.raises(ValueError, match=r"device_profile\.android_id"):
            Korail(device_profile=profile, android_id=different)

        # then
        create.assert_not_called()

    def test_matching_profile_and_explicit_id_are_accepted(self, make_korail) -> None:
        # given
        profile = DEVICE_PROFILES[0]

        # when
        client, _ = make_korail({}, device_profile=profile, android_id=profile.android_id)

        # then
        assert client.android_id == profile.android_id

    def test_constructor_does_no_network_io(self, make_korail) -> None:
        """생성자는 연결만 만들고 요청은 보내지 않아야 합니다."""
        # when
        _, session = make_korail({})

        # then
        assert session.calls == []

    def test_resources_are_attached(self, make_korail) -> None:
        # when
        client, _ = make_korail({})

        # then
        assert client.stations is not None
        assert client.trains is not None
        assert client.reservations is not None
        assert client.tickets is not None

    def test_resources_share_one_session(self, korail) -> None:
        # given
        client, session = korail

        # when
        client.stations.all()
        client.trains.search("서울", "부산")

        # then
        assert client.stations._api is client.trains._api
        assert len(session.calls) == 2

    def test_starts_logged_out(self, make_korail) -> None:
        # when
        client, _ = make_korail({})

        # then
        assert not client.logined
        assert client.membership_number is None


class TestLogin:
    @pytest.mark.parametrize("identity", ["01012345678", "010-1234-5678"])
    def test_complete_login_form_matches_wire_golden(self, make_korail, identity: str) -> None:
        # given
        client, session = make_korail({"code": CIPHER_PAYLOAD, "login": LOGIN_OK})

        # when
        client.login(identity, "pw")

        # then
        request = session.kwargs_for("login")
        form = request["data"]
        assert form["txtPwd"].endswith("\n")
        assert form["idx"] == "7"
        assert {**form, "txtPwd": "<encrypted>", "idx": "<issued>"} == LOGIN_FORM_GOLDEN
        assert set(request) == {"data", "headers"}
        assert set(request["headers"]) == {"x-dynapath-m-token"}

    def test_requests_only_cipher_key_before_login(self, make_korail) -> None:
        # given
        client, session = make_korail({"code": CIPHER_PAYLOAD, "login": LOGIN_OK})

        # when
        client.login("me@example.com", "pw")

        # then
        assert session.urls() == [API_ENDPOINTS["code"], API_ENDPOINTS["login"]]
        assert session.kwargs_for("code")["data"] == {"code": "app.login.cphd"}
        assert session.kwargs_for("login")["data"]["idx"] == "7"

    def test_login_carries_app_version(self, make_korail) -> None:
        # given
        client, session = make_korail({"code": CIPHER_PAYLOAD, "login": LOGIN_OK})

        # when
        client.login("me@example.com", "pw")

        # then
        assert session.kwargs_for("login")["data"]["AppVersion"] == "7.0.8"

    def test_successful_login_populates_account(self, make_korail) -> None:
        # given
        client, _ = make_korail({"code": CIPHER_PAYLOAD, "login": LOGIN_OK})

        # when
        client.login("me@example.com", "pw")

        # then
        assert client.logined
        assert client.membership_number == "1234567890"
        assert client.name == "홍길동"
        assert client.email == "me@example.com"
        assert client.phone_number == "010-1234-5678"

    def test_rejected_credentials_raise(self, make_korail) -> None:
        """반환값으로 알려 주면 확인하지 않은 호출자가 로그인 없이 진행합니다."""
        # given
        client, _ = make_korail({"code": CIPHER_PAYLOAD, "login": LOGIN_FAIL})

        # when & then
        with pytest.raises(LoginFailedError):
            client.login("me@example.com", "pw")

    def test_rejected_login_leaves_the_account_empty(self, make_korail) -> None:
        # given
        client, _ = make_korail({"code": CIPHER_PAYLOAD, "login": LOGIN_FAIL})

        # when
        with pytest.raises(LoginFailedError):
            client.login("me@example.com", "pw")

        # then
        assert not client.logined
        assert client.membership_number is None

    def test_server_reason_is_carried(self, make_korail) -> None:
        """비밀번호 오류와 휴면 계정은 사용자가 해야 할 일이 다릅니다 — 뭉개면 안 됩니다."""
        # given
        client, _ = make_korail({"code": CIPHER_PAYLOAD, "login": LOGIN_FAIL})

        # when
        with pytest.raises(LoginFailedError) as exc:
            client.login("me@example.com", "pw")

        # then
        assert exc.value.msg == "비밀번호가 틀렸습니다"
        assert exc.value.code == "WRC000000"

    def test_falls_back_when_the_server_gives_no_reason(self, make_korail) -> None:
        # given
        client, _ = make_korail({"code": CIPHER_PAYLOAD, "login": {"strResult": "FAIL"}})

        # when
        with pytest.raises(LoginFailedError) as exc:
            client.login("me@example.com", "pw")

        # then
        assert exc.value.msg == "아이디 또는 비밀번호가 올바르지 않습니다"

    @pytest.mark.parametrize("status", [403, 200])
    @pytest.mark.parametrize("code", ["-2000", -2000])
    def test_access_restriction_is_not_reported_as_bad_password(self, make_korail, status: int, code: object) -> None:
        """이용제한을 비밀번호 오류로 바꾸면 사용자가 엉뚱한 것을 고칩니다 (이슈 #27).

        봉투가 HTTP 200 으로 와도 ``LoginFailedError`` 가 아니라 ``AccessRestrictedError`` 입니다.
        """
        # given
        restricted = Reply(status, {**ACCESS_RESTRICTED, "code": code})
        client, _ = make_korail({"code": CIPHER_PAYLOAD, "login": restricted})

        # when
        with pytest.raises(AccessRestrictedError) as exc:
            client.login("me@example.com", "pw")

        # then
        assert (exc.value.status_code, exc.value.code) == (status, "-2000")

    @pytest.mark.parametrize(
        ("korail_id", "expected_flag"),
        [
            ("me@example.com", "5"),  # 이메일
            ("010-1234-5678", "4"),  # 휴대폰
            ("1234567890", "2"),  # 회원번호
        ],
    )
    def test_input_flag_matches_id_shape(self, make_korail, korail_id: str, expected_flag: str) -> None:
        # given
        client, session = make_korail({"code": CIPHER_PAYLOAD, "login": LOGIN_OK})

        # when
        client.login(korail_id, "pw")

        # then
        assert session.kwargs_for("login")["data"]["txtInputFlg"] == expected_flag

    def test_login_is_signed_without_sid(self, make_korail) -> None:
        # given
        client, session = make_korail({"code": CIPHER_PAYLOAD, "login": LOGIN_OK})

        # when
        client.login("me@example.com", "pw")

        # then
        kwargs = session.kwargs_for("login")
        assert "x-dynapath-m-token" in kwargs["headers"]
        assert "Sid" not in kwargs["data"]

    def test_login_password_matches_app_wire_format(self, make_korail) -> None:
        # given
        client, session = make_korail({"code": CIPHER_PAYLOAD, "login": LOGIN_OK})
        cipher_info = CIPHER_PAYLOAD["app.login.cphd"]
        assert isinstance(cipher_info, dict)
        key = cipher_info["key"].encode("utf-8")

        # when
        client.login("me@example.com", "hunter2")

        # then
        password = session.kwargs_for("login")["data"]["txtPwd"]
        assert password.endswith("\n")
        ciphertext = base64.b64decode(base64.b64decode(password[:-1], validate=True), validate=True)
        plaintext = unpad(AES.new(key, AES.MODE_CBC, iv=key[:16]).decrypt(ciphertext), AES.block_size)
        assert plaintext == b"hunter2"

    def test_login_requests_password_validation(self, make_korail) -> None:
        # given
        client, session = make_korail({"code": CIPHER_PAYLOAD, "login": LOGIN_OK})

        # when
        client.login("me@example.com", "pw")

        # then
        assert session.kwargs_for("login")["data"]["checkValidPw"] == "Y"

    def test_missing_credentials_raise(self, make_korail) -> None:
        # given
        client, _ = make_korail({})

        # when & then
        with pytest.raises(LoginFailedError):
            client.login("", "")

    def test_cipher_key_failure_raises(self, make_korail) -> None:
        # given
        client, _ = make_korail({"code": {"strResult": "FAIL", "h_msg_cd": "P999"}})

        # when & then
        with pytest.raises(LoginFailedError):
            client.login("me@example.com", "pw")

    @pytest.mark.parametrize("cipher_info", PARTIAL_CIPHER_INFOS)
    def test_partial_cipher_key_raises_login_failed(self, make_korail, cipher_info: object) -> None:
        """SUCC 여도 키가 덜 오면 KeyError 가 아니라 LoginFailedError 여야 합니다."""
        # given
        client, _ = make_korail({"code": cipher_response(cipher_info)})

        # when & then
        with pytest.raises(LoginFailedError, match="암호화 키"):
            client.login("me@example.com", "pw")

    def test_unusable_cipher_key_raises_login_failed(self, make_korail) -> None:
        """AES 키 길이가 안 맞으면 pycryptodome 의 ValueError 가 새어 나가면 안 됩니다."""
        # given
        client, _ = make_korail({"code": UNUSABLE_CIPHER_PAYLOAD})

        # when & then
        with pytest.raises(LoginFailedError, match="쓸 수 없습니다"):
            client.login("me@example.com", "pw")

    def test_numeric_idx_is_sent_as_a_string(self, make_korail) -> None:
        """``_idx`` 는 ``str | None`` 입니다 — 서버가 숫자로 줘도 폼에는 문자열로 나갑니다."""
        # given
        client, session = make_korail({"code": NUMERIC_IDX_CIPHER_PAYLOAD, "login": LOGIN_OK})

        # when
        client.login("me@example.com", "pw")

        # then
        assert session.kwargs_for("login")["data"]["idx"] == "7"

    def test_login_survives_a_response_without_profile_fields(self, make_korail) -> None:
        """SUCC 와 회원번호를 받았으면 로그인은 된 것입니다 — 이름이 없다고 KeyError 로 죽으면 안 됩니다."""
        # given
        client, _ = make_korail({"code": CIPHER_PAYLOAD, "login": LOGIN_OK_WITHOUT_PROFILE})

        # when
        client.login("me@example.com", "pw")

        # then
        assert (client.logined, client.membership_number) == (True, "1234567890")
        assert (client.name, client.email, client.phone_number) == (None, None, None)

    def test_login_returns_nothing(self, make_korail) -> None:
        """성공 여부를 반환하지 않는 것이 이 메서드의 계약입니다."""
        # given
        client, _ = make_korail({"code": CIPHER_PAYLOAD, "login": LOGIN_OK})

        # when
        result = client.login("me@example.com", "pw")

        # then
        assert result is None


class TestPhoneNormalization:
    """두 휴대폰 입력 형식을 앱의 숫자 전용 폼으로 정규화합니다."""

    @pytest.mark.parametrize("identity", ["031-123-4567", "0311234567", "010-12-3456", "010123456"])
    def test_nonmobile_shapes_are_not_classified_as_mobile(self, make_korail, identity: str) -> None:
        # given
        client, session = make_korail({"code": CIPHER_PAYLOAD, "login": LOGIN_OK})

        # when
        client.login(identity, "pw")

        # then
        form = session.kwargs_for("login")["data"]
        assert form["txtInputFlg"] == "2"
        assert form["txtMemberNo"] == identity

    @pytest.mark.parametrize(
        "korail_id",
        ["01012345678", "01112345678", "0161234567", "01712345678", "01812345678", "01912345678"],
    )
    def test_classifies_hyphenless_mobile_numbers(self, make_korail, korail_id: str) -> None:
        # given
        client, session = make_korail({"code": CIPHER_PAYLOAD, "login": LOGIN_OK})

        # when
        client.login(korail_id, "pw")

        # then
        assert session.kwargs_for("login")["data"]["txtInputFlg"] == "4"
        assert session.kwargs_for("login")["data"]["txtMemberNo"] == korail_id

    @pytest.mark.parametrize("korail_id", ["010-1234-5678", "01012345678"])
    def test_phone_formats_produce_the_same_identity(self, make_korail, korail_id: str) -> None:
        # given
        client, session = make_korail({"code": CIPHER_PAYLOAD, "login": LOGIN_OK})

        # when
        client.login(korail_id, "pw")

        # then
        assert session.kwargs_for("login")["data"]["txtMemberNo"] == "01012345678"

    @pytest.mark.parametrize("korail_id", ["me-name@example.com", "1234567890"])
    def test_preserves_nonphone_identifiers(self, make_korail, korail_id: str) -> None:
        # given
        client, session = make_korail({"code": CIPHER_PAYLOAD, "login": LOGIN_OK})

        # when
        client.login(korail_id, "pw")

        # then
        assert session.kwargs_for("login")["data"]["txtMemberNo"] == korail_id

    @pytest.mark.parametrize("korail_id", ["010-1234-5678", "1234567890", "me@example.com"])
    def test_allows_valid_id_shapes(self, make_korail, korail_id: str) -> None:
        # given
        client, _ = make_korail({"code": CIPHER_PAYLOAD, "login": LOGIN_OK})

        # when
        client.login(korail_id, "pw")

        # then
        assert client.logined


class TestLoggedInFactory:
    def test_factory_restores_explicit_android_id(self, monkeypatch, make_korail) -> None:
        # given
        _, session = make_korail({"code": CIPHER_PAYLOAD, "login": LOGIN_OK})
        monkeypatch.setattr("pykorail.client.create_session", lambda headers: session)

        # when
        client = Korail.logged_in("me@example.com", "pw", android_id="0123456789abcdef")

        # then
        assert client.android_id == "0123456789abcdef"
        token = session.kwargs_for("login")["headers"]["x-dynapath-m-token"]
        assert dict(parse_qsl(decode_token(token)[1]))["di"] == client.android_id

    def test_returns_logged_in_client(self, monkeypatch, make_korail) -> None:
        # given
        _, session = make_korail({"code": CIPHER_PAYLOAD, "login": LOGIN_OK})
        monkeypatch.setattr("pykorail.client.create_session", lambda headers: session)

        # when
        client = Korail.logged_in("me@example.com", "pw")

        # then
        assert client.logined

    def test_bad_credentials_raise_and_close(self, monkeypatch, make_korail) -> None:
        # given
        _, session = make_korail({"code": CIPHER_PAYLOAD, "login": LOGIN_FAIL})
        monkeypatch.setattr("pykorail.client.create_session", lambda headers: session)

        # when
        with pytest.raises(LoginFailedError):
            Korail.logged_in("me@example.com", "wrong")

        # then
        assert session.closed, "실패했으면 연결을 흘리지 말아야 합니다"


class TestLifecycle:
    def test_logout_clears_account_but_keeps_connection(self, make_korail) -> None:
        # given
        client, session = make_korail({"code": CIPHER_PAYLOAD, "login": LOGIN_OK, "logout": {"strResult": "SUCC"}})
        client.login("me@example.com", "pw")

        # when
        client.logout()

        # then
        assert not client.logined
        assert client.membership_number is None
        assert not session.closed, "로그아웃은 연결을 끊지 않습니다"

    def test_can_log_in_again_after_logout(self, make_korail) -> None:
        # given
        client, _ = make_korail({"code": CIPHER_PAYLOAD, "login": LOGIN_OK, "logout": {"strResult": "SUCC"}})
        client.login("me@example.com", "pw")
        client.logout()

        # when
        client.login("me@example.com", "pw")

        # then
        assert client.logined

    def test_context_manager_closes_session(self, make_korail) -> None:
        # given
        client, session = make_korail({})

        # when
        with client:
            pass

        # then
        assert session.closed

    def test_logout_url(self, make_korail) -> None:
        # given
        client, session = make_korail({"logout": {"strResult": "SUCC"}})

        # when
        client.logout()

        # then
        assert session.urls() == [API_ENDPOINTS["logout"]]


class TestDeviceProfile:
    def test_profile_sets_signature_but_keeps_app_user_agent(self, monkeypatch) -> None:
        # given
        from pykorail.device import DeviceProfile
        from tests.conftest import FakeSession

        captured: dict[str, str] = {}

        def fake_create_session(headers: dict[str, str]) -> FakeSession:
            captured.update(headers)
            return FakeSession({})

        monkeypatch.setattr("pykorail.client.create_session", fake_create_session)
        profile = DeviceProfile(
            id="s21-a15",
            marketing="Galaxy S21",
            model="SM-G991N",
            android="15",
            build_id="AP3A.240905.015.A2",
        )

        # when
        client = Korail(device_profile=profile)

        # then
        assert captured["User-Agent"] == "korailtalk"
        engine = client._api._signer._engine
        assert engine.device_model == "SM-G991N"
        assert engine.os_version == "15"
        assert client._api._signer._device_id == profile.android_id

    def test_default_client_uses_same_app_user_agent(self, monkeypatch) -> None:
        # given
        from tests.conftest import FakeSession

        create = Mock(return_value=FakeSession({}))
        monkeypatch.setattr("pykorail.client.create_session", create)

        # when
        Korail()

        # then
        assert create.call_args.args[0]["User-Agent"] == "korailtalk"

    def test_default_headers_are_not_mutated(self, make_korail) -> None:
        # given
        from pykorail.constants import DEFAULT_HEADERS
        from pykorail.device import DeviceProfile

        before = dict(DEFAULT_HEADERS)
        profile = DeviceProfile(id="x", marketing="x", model="SM-S921N", android="15", build_id="AP3A.240905.015.A2")

        # when
        make_korail({}, device_profile=profile)

        # then
        assert before == DEFAULT_HEADERS

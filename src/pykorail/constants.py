"""코레일 스마트 앱 API 의 고정 상수.

여기 있는 값들은 실제 앱 트래픽에서 관찰·디컴파일로 확인된 것입니다.
**동작하는 값을 근거 없이 바꾸지 마세요** — 서버가 앱 버전·기기 문자열을 게이트로
볼 수 있습니다.
"""

from __future__ import annotations

import re
from typing import Final

EMAIL_REGEX: Final = re.compile(r"[^@]+@[^@]+\.[^@]+")
PHONE_NUMBER_REGEX: Final = re.compile(r"01[016789]-\d{3,4}-\d{4}")

#: 하이픈 없는 번호도 txtInputFlg=4로 분류해 회원번호와 구분합니다.
HYPHENLESS_PHONE_REGEX: Final = re.compile(r"^01[016789]\d{7,8}$")

API_HOST: Final = "smart.letskorail.com"

#: 스마트 앱 API의 공통 User-Agent. 기기 프로파일도 이 값을 바꾸지 않습니다.
USER_AGENT: Final = "korailtalk"

DEFAULT_HEADERS: Final[dict[str, str]] = {
    "Content-Type": "application/x-www-form-urlencoded",
    "User-Agent": USER_AGENT,
    "Host": API_HOST,
    "Connection": "Keep-Alive",
    "Accept-Encoding": "gzip",
}

KORAIL_MOBILE: Final = f"https://{API_HOST}:443/classes/com.korail.mobile"

#: DynaPath 서명(``x-dynapath-m-token``) 대상 경로. Sid 전송 여부는 각 호출에서 결정합니다.
DYNAPATH_PATHS: Final[tuple[str, ...]] = (
    "/classes/com.korail.mobile.certification.TicketReservation",
    "/classes/com.korail.mobile.nonMember.NonMemTicket",
    "/classes/com.korail.mobile.seatMovie.ScheduleView",
    "/classes/com.korail.mobile.seatMovie.ScheduleViewSpecial",
    "/classes/com.korail.mobile.trn.prcFare.do",
    "/classes/com.korail.mobile.login.Login",
)

API_ENDPOINTS: Final[dict[str, str]] = {
    "login": f"{KORAIL_MOBILE}.login.Login",
    "logout": f"{KORAIL_MOBILE}.common.logout",
    "search_schedule": f"{KORAIL_MOBILE}.seatMovie.ScheduleView",
    "reserve": f"{KORAIL_MOBILE}.certification.TicketReservation",
    "cancel": f"{KORAIL_MOBILE}.reservationCancel.ReservationCancelChk",
    "myticketseat": f"{KORAIL_MOBILE}.refunds.SelTicketInfo",
    "myticketlist": f"{KORAIL_MOBILE}.myTicket.MyTicketList",
    "myreservationview": f"{KORAIL_MOBILE}.reservation.ReservationView",
    "myreservationlist": f"{KORAIL_MOBILE}.certification.ReservationList",
    "pay": f"{KORAIL_MOBILE}.payment.ReservationPayment",
    "refund": f"{KORAIL_MOBILE}.refunds.RefundsRequest",
    # 환불 수수료 사전조회. RefundsRequest 와 같은 refunds 패키지지만 폼 필드
    # 이름이 다릅니다 — 아래 refund_fee() 주석 참고.
    "refund_commission": f"{KORAIL_MOBILE}.refunds.CommissionView",
    "code": f"{KORAIL_MOBILE}.common.code.do",
    "stationdata": f"{KORAIL_MOBILE}.common.stationdata",
}

# --------------------------------------------------------------- 앱 신원값
DEVICE: Final = "AD"
APP_VERSION: Final = "250722001"
#: API의 Version과 별개인 공식 앱 표시 버전입니다.
APP_DISPLAY_VERSION: Final = "7.0.8"
API_KEY: Final = "korail1234567890"
SID_KEY: Final = b"2485dd54d9deaa36"

#: curl_cffi의 기존 TLS 타깃입니다. HTTP 헤더는 앱 기준으로 별도 지정합니다.
IMPERSONATE: Final = "chrome131_android"

#: 한국 표준시(UTC+9). 코레일 API 의 모든 날짜·시각은 KST 기준입니다.
KST_OFFSET_HOURS: Final = 9

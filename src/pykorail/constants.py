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
    # 운행 달력. 노선·날짜 인자 없이 오늘부터 약 두 달치를 돌려줍니다.
    "run_dates": f"{KORAIL_MOBILE}.schedule.runDt",
    "transfer_stations": f"{KORAIL_MOBILE}.qry.chtnStn.do",
    "fare": f"{KORAIL_MOBILE}.trn.prcFare.do",
    "seat_cars": f"{KORAIL_MOBILE}.research.TrainResearch",
    "seat_map": f"{KORAIL_MOBILE}.research.TResidualSeatsResearch.do",
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
    "bus_schedule": f"{KORAIL_MOBILE}.lmu.scdlQry.do",
    "bus_seat_map": f"{KORAIL_MOBILE}.lms.TResidualSeatsResearch.do",
    "mileage": f"{KORAIL_MOBILE}.mlg.amtSpec.do",
    "coupons": f"{KORAIL_MOBILE}.passCard.CouponView",
    "code": f"{KORAIL_MOBILE}.common.code.do",
    "stationdata": f"{KORAIL_MOBILE}.common.stationdata",
}

# --------------------------------------------------------------- 앱 신원값
DEVICE: Final = "AD"
APP_VERSION: Final = "250722001"
#: API의 Version과 별개인 공식 앱 표시 버전입니다.
#: 서버가 이 값으로 최신 버전을 강제하므로(AppVersion), 오래된 값은 -8204로 거절됩니다.
APP_DISPLAY_VERSION: Final = "7.0.10"
API_KEY: Final = "korail1234567890"
SID_KEY: Final = b"2485dd54d9deaa36"

# --------------------------------------------------------------- DynaPath (7.0.10)
#: 7.0.10 ``x-dynapath-m-token`` 의 버전 프리픽스. 서버는 이 프리픽스로 버전을 가릅니다.
TOKEN_PREFIX: Final = "201"
#: 네이티브 ``declarationToken`` 의 소프트웨어 선언 op id(``kr.scripters.dynapath.sdk.android.a.J0``).
#: 이 엔진이 기본으로 쓰는 선언 op. 캡처된 실측 토큰은 다른 op(893617653734745139)를 썼지만, 이 op
#: 는 실서버 전체 흐름에서 수용 확인됐고 J0 분석의 소프트웨어 선언 op 다(ec=978212327729758430 동반).
#: ``es``(op)·봉투 필드 집합은 operation/상태에 따라 달라집니다 — 토큰 생성 알고리즘(키스트림·MAC·
#: base62)은 실측 캡처로 바이트 동일 재현을 확인했습니다(``auth/dynapath.py`` 참조). 엔드포인트별
#: 선언 op 는 없습니다(``auth/signer.py``).
DYNAPATH_LOGIN_OP: Final = 288904575606514493
#: v2 선언 봉투의 ``sv=``(DynaPath SDK 버전)·``ai=``(앱 식별자). 실토큰 엔진이 쓰는
#: wire 값으로, APP_VERSION(API Version)과는 별개입니다. 근거: ``docs/protocol-evidence-7.0.10.json``.
DYNAPATH_SDK_VERSION: Final = "2.0.1"
DYNAPATH_APP_ID: Final = "korailplus"

#: curl_cffi의 기존 TLS 타깃입니다. HTTP 헤더는 앱 기준으로 별도 지정합니다.
IMPERSONATE: Final = "chrome131_android"

#: 한국 표준시(UTC+9). 코레일 API 의 모든 날짜·시각은 KST 기준입니다.
KST_OFFSET_HOURS: Final = 9

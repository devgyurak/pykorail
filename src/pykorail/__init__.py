"""pykorail — 코레일(KTX) 스마트 예매 비공식 Python 클라이언트.

::

    from pykorail import AdultPassenger, ChildPassenger, Korail
    from pykorail.device import profile_by_id, random_profile

    profile = profile_by_id(saved_id, android_id=saved_android_id) or random_profile()
    with Korail.logged_in("me@example.com", "password", device_profile=profile) as korail:
        trains = korail.trains.search("서울", "부산", passengers=[AdultPassenger(2), ChildPassenger(1)])
        reservation = korail.reservations.create(trains[0])

API 는 리소스별로 나뉘어 있습니다 — ``korail.stations`` / ``korail.trains`` /
``korail.reservations`` / ``korail.tickets``. 로그인·로그아웃·연결 정리만
:class:`~pykorail.client.Korail` 본체에 있습니다.

하위 모듈:
    - :mod:`pykorail.device` — 기기 프로파일 카탈로그 (주입용)
    - :mod:`pykorail.exceptions` — 예외 계층
    - :mod:`pykorail.models` — 불변 응답 모델
    - :mod:`pykorail.options` — 조회·예매 옵션 코드
    - :mod:`pykorail.resources` — 리소스 구현
    - :mod:`pykorail.auth` — DynaPath 서명, NetFunnel 대기열
"""

from __future__ import annotations

from importlib import metadata

from pykorail import _compat as _compat  # 최소 파이썬 버전 강제 — 다른 임포트보다 먼저
from pykorail.auth import NetFunnelHelper
from pykorail.client import Korail
from pykorail.device import DeviceProfile, DeviceProfileLike, profile_by_id, random_profile
from pykorail.exceptions import (
    KorailError,
    LoginFailedError,
    NeedToLoginError,
    NetFunnelError,
    NoResultsError,
    PastDepartureError,
    PykorailError,
    SoldOutError,
    StationNotFoundError,
    TransportError,
)
from pykorail.models import (
    AdultPassenger,
    Card,
    ChildPassenger,
    Disability1To3Passenger,
    Disability4To6Passenger,
    Passenger,
    RefundFee,
    Reservation,
    Schedule,
    Seat,
    SeniorPassenger,
    Station,
    Ticket,
    ToddlerPassenger,
    Train,
)
from pykorail.options import ReserveOption, ReserveOptionCode, TrainType, TrainTypeCode


def _resolve_version() -> str:
    """설치된 배포 메타데이터에서 버전을 읽습니다.

    버전의 유일한 출처는 **git 태그**입니다 (hatch-vcs). 소스에 숫자를 박아 두면
    태그와 어긋나므로 여기서 하드코딩하지 않습니다. 빌드 훅이 `_version.py` 를
    만들어 두므로 설치 후에는 git 없이도 읽힙니다.
    """
    try:
        from pykorail._version import __version__ as built_version
    except ImportError:
        pass
    else:
        return built_version

    try:
        return metadata.version("pykorail")
    except metadata.PackageNotFoundError:
        # 설치하지 않고 소스 트리에서 바로 임포트한 경우.
        return "0.0.0+unknown"


__version__ = _resolve_version()

__all__ = [
    "AdultPassenger",
    "Card",
    "ChildPassenger",
    "DeviceProfile",
    "DeviceProfileLike",
    "Disability1To3Passenger",
    "Disability4To6Passenger",
    "Korail",
    "KorailError",
    "LoginFailedError",
    "NeedToLoginError",
    "NetFunnelError",
    "NetFunnelHelper",
    "NoResultsError",
    "Passenger",
    "PastDepartureError",
    "PykorailError",
    "RefundFee",
    "Reservation",
    "ReserveOption",
    "ReserveOptionCode",
    "Schedule",
    "Seat",
    "SeniorPassenger",
    "SoldOutError",
    "Station",
    "StationNotFoundError",
    "Ticket",
    "ToddlerPassenger",
    "Train",
    "TrainType",
    "TrainTypeCode",
    "TransportError",
    "__version__",
    "profile_by_id",
    "random_profile",
]

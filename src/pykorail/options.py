"""조회·예매 옵션 코드.

``Enum`` 이 아니라 문자열 상수인 것은 의도적입니다 — 이 값들은 폼 필드에 그대로
실려 나가는데, ``str`` 을 섞은 ``Enum`` 은 파이썬 버전에 따라 ``str()`` 결과가
``"TrainType.KTX"`` 로 나와 전송 값이 조용히 깨집니다.

대신 :data:`TrainTypeCode` · :data:`ReserveOptionCode` 같은 리터럴 별칭으로 오타를
정적으로 잡습니다 — ``train_type="999"`` 는 타입 검사에서 걸립니다.
"""

from __future__ import annotations

from typing import Final, Literal

#: 유효한 열차 종별 코드. :class:`TrainType` 의 상수들이 이 집합을 이룹니다.
TrainTypeCode = Literal["100", "101", "102", "103", "104", "105", "109"]

#: 유효한 특실/일반실 선택 전략.
ReserveOptionCode = Literal["GENERAL_FIRST", "GENERAL_ONLY", "SPECIAL_FIRST", "SPECIAL_ONLY"]

#: 유효한 객실 구분 코드.
SeatClassCode = Literal["1", "2"]

#: 유효한 마일리지 종류 코드.
MileageTypeCode = Literal["1", "2"]

#: 유효한 마일리지 내역 구분 코드.
MileageInquiryCode = Literal["0", "1", "2"]

#: 유효한 NetFunnel 대기열 동작 코드(``aid``). :class:`NetFunnelAction` 의 상수들이 이 집합을 이룹니다.
NetFunnelActionCode = Literal["act_8", "act_8_2", "act_6", "act_14", "act_14_2", "act_18", "act_21"]


class TrainType:
    """``selGoTrain``/``txtTrnGpCd`` 열차 종별 코드.

    KTX 와 KTX-산천은 같은 코드(``100``)를 씁니다 — 별칭이지 오타가 아닙니다.
    """

    KTX: Final = "100"
    KTX_SANCHEON: Final = "100"
    SAEMAEUL: Final = "101"
    ITX_SAEMAEUL: Final = "101"
    MUGUNGHWA: Final = "102"
    NURIRO: Final = "102"
    TONGGUEN: Final = "103"
    ITX_CHEONGCHUN: Final = "104"
    AIRPORT: Final = "105"
    ALL: Final = "109"


class ReserveOption:
    """특실/일반실 선택 전략."""

    GENERAL_FIRST: Final = "GENERAL_FIRST"
    GENERAL_ONLY: Final = "GENERAL_ONLY"
    SPECIAL_FIRST: Final = "SPECIAL_FIRST"
    SPECIAL_ONLY: Final = "SPECIAL_ONLY"


class SeatClass:
    """객실 구분 코드 (``psrmClCd``). 호차·좌석 조회에 그대로 실립니다."""

    GENERAL: Final = "1"
    SPECIAL: Final = "2"


class MileageType:
    """마일리지 종류 코드 (``pontTpVal``). 내역을 볼 장부를 고릅니다.

    코레일+ 7.0.8 의 ``MileageType`` 이 서버로 보내는 값입니다.
    """

    KTX: Final = "1"
    RAIL_POINT: Final = "2"


class MileageInquiry:
    """마일리지 내역 구분 코드 (``qryDvVal``). 앱의 "조회 유형"입니다.

    코레일+ 7.0.8 의 ``MileageInquiryType`` 이 서버로 보내는 값입니다.
    """

    ALL: Final = "0"
    SAVE: Final = "1"
    USE: Final = "2"


class NetFunnelAction:
    """NetFunnel ``5101`` 요청의 ``aid`` — 대기열을 통과할 대상 동작.

    코레일톡+ 7.0.8 의 ``NetworkConstants$Netfunnel`` 상수를 AlienGuard 복호 결과로
    옮긴 값입니다(암호문·근거는 ``docs/protocol-evidence-7.0.8.json`` 의
    ``netfunnel.actions``). ``aid`` 가 다르면 같은 대기열이 아니므로 통과 티켓을
    섞어 쓸 수 없습니다.

    열차 조회는 조건에 따라 ``TRAIN_SEARCH`` · ``TRAIN_SEARCH_PEAK`` ·
    ``TRAIN_SEARCH_SPECIAL_OFFER`` 중 하나를, 예약은 7.1.0 부터 ``RESERVE`` ·
    ``RESERVE_PEAK`` 중 하나를 고릅니다. 성수기 판정은 ``schedule.runDt`` 응답의
    성수기 플래그에 달려 있어 호출자가 정합니다 —
    :func:`~pykorail.models.run_date.netfunnel_action_for` 에 평시 aid 를 ``action`` 으로
    넘기세요(조회는 출발일, 예약은 운행일 기준).
    """

    #: 열차 조회 (평시). 앱 ``TrainScheduleViewModel.netFunnelTrainSchedule``.
    #: 출발일의 ``bizDdStgCd`` 가 ``"5"`` 가 아니거나 조회일 항목이 없을 때도 이 값을 씁니다.
    TRAIN_SEARCH: Final = "act_8"
    #: 열차 조회 (성수기). 출발일의 ``bizDdStgCd`` 가 ``"5"`` 일 때 씁니다.
    TRAIN_SEARCH_PEAK: Final = "act_8_2"
    #: 열차 조회 (할인상품). 앱에서 ``ACCOMPANY_4`` 가 아닌 할인상품을 골랐을 때.
    TRAIN_SEARCH_SPECIAL_OFFER: Final = "act_6"
    #: 예약 (평시). 7.0.10 까지는 예약 화면 네 곳(``TrainScheduleViewModel`` ·
    #: ``TrainSeatMapViewModel`` · ``ReservationWaitViewModel`` · ``HomeViewModel``)이 이
    #: 값을 직접 넣었고, 7.1.0 부터는 네 곳 모두 ``NetFunnelHelper.reserveNetFunnelActionId``
    #: 를 거칩니다 — 첫 여정의 운행일이 성수기가 아니거나 달력에 그날이 없을 때의 값입니다.
    RESERVE: Final = "act_14"
    #: 예약 (성수기). 7.1.0 의 ``reserveNetFunnelActionId`` 가 첫 여정의 운행일
    #: (``txtRunDt``)이 성수기면 쓰는 값입니다(``docs/protocol-evidence-7.1.0.json``).
    RESERVE_PEAK: Final = "act_14_2"
    #: 결제. ``PayViewModel`` · ``FPayViewModel``.
    PAY: Final = "act_18"
    #: 내 예약 조회. ``MyReservationViewModel``.
    RESERVATION_VIEW: Final = "act_21"

"""운행 달력(``schedule.runDt``) 응답 모델.

코레일은 오늘부터 약 두 달치의 날짜별 운행 정보를 돌려줍니다. 항목마다 그날이
성수기인지(``biz_dd_stg_cd``)를 담고 있어, NetFunnel 대기열의 ``aid`` 를 고르는
근거가 됩니다 — 어느 값을 쓸지는 :func:`netfunnel_action_for` 가 정합니다.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import TYPE_CHECKING, Any

from pykorail._shared.clock import to_kst
from pykorail.models.parsing import kst_date, text
from pykorail.options import NetFunnelAction

if TYPE_CHECKING:
    from collections.abc import Sequence
    from typing import Self

    from pykorail.options import NetFunnelActionCode

#: 성수기를 뜻하는 ``bizDdStgCd``. 코레일+ 7.0.8 의 ``RunDateOutItem.isPeakSeason`` 이
#: 등호 비교라는 것은 정적 분석으로 확인했고, 상수 ``"5"`` 는 캡처에서 유도했습니다
#: (#117). 실측이 확인한 것은 ``1``–``3`` 이 ``act_8`` 로 이어진다는 점뿐입니다.
_PEAK_SEASON = "5"


@dataclass(frozen=True)
class RunDate:
    """운행 달력의 하루.

    ``run_date`` 와 ``is_peak_season`` 만 뜻을 확인했습니다. 나머지 필드는 의미를
    확인하지 못해 **앱 ``RunDateOutItem`` 의 원문 필드명을 snake_case 로 옮긴 이름**에
    원문 문자열을 담습니다 — ``day_dv_cd`` · ``hldy_dv_cd`` · ``sale_dd_dv_cd`` 와
    ``*TrnOpFlg`` 입니다. 플래그는 ``"Y"`` · ``"N"`` 외에 빈 문자열(``""``)도 오므로
    불리언으로 바꾸지 않습니다.
    """

    run_date: str
    biz_dd_stg_cd: str
    day_dv_cd: str
    hldy_dv_cd: str
    sale_dd_dv_cd: str
    o_trn_op_flg: str
    v_trn_op_flg: str
    s_trn_op_flg: str
    d_trn_op_flg: str
    a_trn_op_flg: str
    g_trn_op_flg: str
    x_trn_op_flg: str

    @classmethod
    def from_response(cls, data: dict[str, Any]) -> Self:
        return cls(
            run_date=text(data, "runDt"),
            biz_dd_stg_cd=text(data, "bizDdStgCd"),
            day_dv_cd=text(data, "dayDvCd"),
            hldy_dv_cd=text(data, "hldyDvCd"),
            sale_dd_dv_cd=text(data, "saleDdDvCd"),
            o_trn_op_flg=text(data, "oTrnOpFlg"),
            v_trn_op_flg=text(data, "vTrnOpFlg"),
            s_trn_op_flg=text(data, "sTrnOpFlg"),
            d_trn_op_flg=text(data, "dTrnOpFlg"),
            a_trn_op_flg=text(data, "aTrnOpFlg"),
            g_trn_op_flg=text(data, "gTrnOpFlg"),
            x_trn_op_flg=text(data, "xTrnOpFlg"),
        )

    @property
    def day(self) -> date | None:
        """운행일을 날짜로. 형식이 틀리면 ``None``."""
        return kst_date(self.run_date)

    @property
    def is_peak_season(self) -> bool:
        """성수기 운행일인지. ``biz_dd_stg_cd`` 가 ``"5"`` 일 때 참입니다 (#117)."""
        return self.biz_dd_stg_cd == _PEAK_SEASON


#: 성수기에 따로 서는 대기열. 키는 평시 aid, 값은 그 성수기 aid 입니다. 열차 조회는
#: 7.0.8 부터, 예약은 7.1.0 부터 갈립니다(``docs/protocol-evidence-7.1.0.json``).
#: 할인상품 조회 · 결제 · 내 예약 조회는 앱이 성수기와 무관하게 같은 aid 를 씁니다.
_PEAK_QUEUES: dict[NetFunnelActionCode, NetFunnelActionCode] = {
    NetFunnelAction.TRAIN_SEARCH: NetFunnelAction.TRAIN_SEARCH_PEAK,
    NetFunnelAction.RESERVE: NetFunnelAction.RESERVE_PEAK,
}


def netfunnel_action_for(
    run_dates: Sequence[RunDate],
    departure: date | datetime | str,
    *,
    action: NetFunnelActionCode = NetFunnelAction.TRAIN_SEARCH,
) -> NetFunnelActionCode:
    """기준일이 성수기인지 운행 달력에서 보고 ``action`` 의 NetFunnel ``aid`` 를 고릅니다.

    성수기면 ``action`` 의 성수기 대기열, 그 밖이거나 달력에 그날이 없으면 ``action``
    그대로입니다. 성수기 대기열이 따로 있는 동작은 둘입니다.

    - 열차 조회(``TRAIN_SEARCH``, 기본) → ``TRAIN_SEARCH_PEAK``(``act_8_2``). 기준일은
      **조회 조건의 출발일**입니다 — 앱 ``TrainScheduleViewModel.netFunnelTrainSchedule``.
    - 예약(``RESERVE``) → ``RESERVE_PEAK``(``act_14_2``, 7.1.0 부터). 기준일은 **첫
      여정 열차의 운행일**(``Train.run_date``)입니다 — 앱
      ``NetFunnelHelper.reserveNetFunnelActionId`` 가 ``txtRunDt`` 로 판정하고, 그것이
      비었을 때만 ``txtDptDt`` 를 씁니다. 자정을 넘겨 출발하는 열차는 운행일과 출발일이
      다르므로 출발일을 넘기면 틀린 대기열을 고를 수 있습니다.

    그 밖의 동작은 성수기 대기열이 없어 ``action`` 을 그대로 돌려줍니다.

    ``departure`` 는 ``date`` · ``datetime`` · ``"YYYYMMDD"`` 문자열을 받습니다. 문자열은
    응답 모델의 날짜 필드(``Train.run_date`` 등)를 그대로 넘기라고 받으며, 형식이 틀리면
    ``ValueError`` 입니다. ``datetime`` 은 KST 로 바꿔 날짜만 봅니다::

        calendar = korail.trains.run_dates()
        aid = netfunnel_action_for(calendar, departure)
        reserve_aid = netfunnel_action_for(calendar, train.run_date or train.dep_date, action=NetFunnelAction.RESERVE)
    """
    wanted = _kst_date(departure)
    matched = next((day for day in run_dates if day.day == wanted), None)
    if matched is not None and matched.is_peak_season:
        return _PEAK_QUEUES.get(action, action)
    return action


def _kst_date(departure: date | datetime | str) -> date:
    """``datetime`` 은 KST 로 변환한 날짜, ``"YYYYMMDD"`` 는 그 날짜, ``date`` 는 그대로."""
    if isinstance(departure, str):
        day = kst_date(departure)
        if day is None:
            # 형식이 틀린 날짜를 "달력에 없음" 으로 넘기면 조용히 평시 대기열로 갑니다.
            raise ValueError(f"기준일은 YYYYMMDD 형식이어야 합니다: {departure!r}")
        return day
    # ``datetime`` 이 ``date`` 의 하위 타입이라 순서를 지켜야 합니다.
    return to_kst(departure).date() if isinstance(departure, datetime) else departure

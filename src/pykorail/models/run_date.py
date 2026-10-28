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


def netfunnel_action_for(
    run_dates: Sequence[RunDate], departure: date | datetime, *, reserve: bool = False
) -> NetFunnelActionCode:
    """출발일의 NetFunnel 대기열 ``aid`` 를 운행 달력에서 고릅니다.

    열차 조회(기본)는 출발일이 성수기면 ``TRAIN_SEARCH_PEAK``(``act_8_2``), 그 밖이거나
    달력에 그날이 없으면 ``TRAIN_SEARCH``(``act_8``) 입니다. ``reserve=True`` 면 예약
    대기열을 같은 규칙으로 골라 ``RESERVE_PEAK``(``act_14_2``) 또는 ``RESERVE``(``act_14``)
    입니다 — 코레일톡+ 7.1.0 의 ``NetFunnelHelper.reserveNetFunnelActionId`` 가 첫 여정의
    운행일로 이렇게 판정합니다. ``datetime`` 은 KST 로 바꿔 날짜만 보므로 tz 가 붙어
    있어도 한국 시간 기준 날짜로 판정합니다.

    :meth:`Korail.trains.run_dates` 의 결과를 그대로 넘기세요::

        calendar = korail.trains.run_dates()
        aid = netfunnel_action_for(calendar, departure)
        reserve_aid = netfunnel_action_for(calendar, departure, reserve=True)
    """
    wanted = _kst_date(departure)
    matched = next((day for day in run_dates if day.day == wanted), None)
    peak = matched is not None and matched.is_peak_season
    if reserve:
        return NetFunnelAction.RESERVE_PEAK if peak else NetFunnelAction.RESERVE
    return NetFunnelAction.TRAIN_SEARCH_PEAK if peak else NetFunnelAction.TRAIN_SEARCH


def _kst_date(departure: date | datetime) -> date:
    """``datetime`` 은 KST 로 변환한 날짜, ``date`` 는 그대로."""
    # ``datetime`` 이 ``date`` 의 하위 타입이라 순서를 지켜야 합니다.
    return to_kst(departure).date() if isinstance(departure, datetime) else departure

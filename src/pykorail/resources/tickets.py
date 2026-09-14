"""승차권 리소스."""

from __future__ import annotations

from typing import Any

from pykorail.constants import API_ENDPOINTS
from pykorail.exceptions import NoResultsError
from pykorail.models.refund import RefundFee
from pykorail.models.ticket import Ticket, train_info_of
from pykorail.resources.base import Resource

#: 좌석 상세 조회에 되돌려 줘야 하는 원권(原券) 식별자. 하나도 없으면 조회할 근거가 없습니다.
_ORIGINAL_TICKET_KEYS = ("h_orgtk_wct_no", "h_orgtk_ret_sale_dt", "h_orgtk_sale_sqno", "h_orgtk_ret_pwd")


class TicketResource(Resource):
    """``korail.tickets`` — 발권된 승차권 조회·환불."""

    def all(self) -> list[Ticket]:
        """발권 완료된 승차권 목록. 없으면 빈 리스트.

        목록 응답에는 실제 좌석번호가 없어 승차권마다 상세를 한 번 더 조회하고,
        **좌석까지 확정한 뒤** 승차권 객체를 만듭니다.
        """
        payload = self._api.get(
            API_ENDPOINTS["myticketlist"],
            params={
                **self._api.base_payload(),
                "txtDeviceId": "",
                "txtIndex": "1",
                "h_page_no": "1",
                "h_abrd_dt_from": "",
                "h_abrd_dt_to": "",
                "hiduserYn": "Y",
            },
        )
        # "승차권이 없다" 로 해석해도 되는 것은 **목록 응답**의 NoResults 뿐입니다.
        # 아래 상세 조회까지 이 try 로 감싸면 좌석 조회 한 건이 실패했을 때 이미
        # 읽어 둔 승차권까지 통째로 사라져, 사용자에게는 "승차권 없음" 으로 보입니다.
        try:
            self._api.check(payload)
        except NoResultsError:
            return []

        # 좌석 상세 조회에 원본 dict 가 필요해서 Ticket.from_ticket_list() 가 아니라
        # 언래핑 헬퍼를 직접 씁니다 — 둘 다 같은 train_info_of() 위에 서 있습니다.
        raws = [train_info_of(entry) for entry in payload.get("reservation_list", [])]
        return [Ticket.from_response(raw, seat_no=self._seat_no(raw)) for raw in raws if raw is not None]

    def _seat_no(self, raw: dict[str, Any]) -> str | None:
        """승차권 상세 조회로 실제 좌석번호를 확인합니다. 없으면 ``None``.

        상세 조회는 목록 응답을 **보강할 뿐**이라, 결과가 없어도 승차권 자체는
        유효합니다. 그래서 NoResults 는 밖으로 내보내지 않고 ``None`` 으로 접어
        목록 응답의 좌석번호로 되돌아갑니다 — 승차권 한 장의 상세가 비었다고 목록
        전체가 비어 보이면 안 됩니다. 그 밖의 실패(만료된 세션 등)는 진짜 문제이므로
        그대로 올립니다.

        원권 식별자가 하나도 없으면 요청 자체를 보내지 않습니다 — 네 값이 전부
        ``None`` 인 조회는 서버가 돌려줄 것이 없는데 요청만 축냅니다. 하나라도
        있으면 예전처럼 그대로 실어 보냅니다(부분 응답에도 조회가 되던 경로를
        막지 않으려는 것입니다).
        """
        if not any(raw.get(key) for key in _ORIGINAL_TICKET_KEYS):
            return None

        payload = self._api.get(
            API_ENDPOINTS["myticketseat"],
            params={
                **self._api.base_payload(),
                "h_orgtk_wct_no": raw.get("h_orgtk_wct_no"),
                "h_orgtk_ret_sale_dt": raw.get("h_orgtk_ret_sale_dt"),
                "h_orgtk_sale_sqno": raw.get("h_orgtk_sale_sqno"),
                "h_orgtk_ret_pwd": raw.get("h_orgtk_ret_pwd"),
            },
        )
        try:
            self._api.check(payload)
        except NoResultsError:
            return None

        ticket_info = payload.get("ticket_infos", {}).get("ticket_info", [{}])[0]
        seat = ticket_info.get("tk_seat_info", [{}])[0]
        return seat.get("h_seat_no")

    def refund_fee(self, ticket: Ticket) -> RefundFee:
        """환불하면 수수료가 얼마인지 **조회만** 합니다. 환불하지 않습니다.

        폼 필드 이름이 :meth:`refund` 와 다릅니다. 같은 ``refunds`` 패키지인데도
        판매일자는 ``h_orgtk_ret_sale_dt``(``refund`` 는 ``h_orgtk_sale_dt``),
        창구번호는 ``h_orgtk_wct_no``(``refund`` 는 ``h_orgtk_sale_wct_no``)
        입니다. **네 철자가 APK 안에 전부 실재하므로 헷갈리면 조용한 빈 값이
        됩니다** — 통일하지 마세요.

        ``h_comp_*``(동반자)와 ``ctlDvCd``·``lang`` 은 앱이 기본값으로 빈 문자열을
        보냅니다. 빼지 말고 빈 값으로 실으세요.

        코레일톡+ 7.0.1 의 ``RefundCommissionIn`` 에서 확인했습니다.

        Raises:
            KorailError: 조회가 거부됐습니다.
        """
        payload = self._api.post(
            API_ENDPOINTS["refund_commission"],
            data={
                **self._api.base_payload(),
                "h_orgtk_ret_sale_dt": ticket.sale_info2,
                "h_orgtk_wct_no": ticket.sale_info1,
                "h_orgtk_sale_sqno": ticket.sale_info3,
                "h_orgtk_ret_pwd": ticket.sale_info4,
                "h_comp_nm": "",
                "h_comp_cert_no": "",
                "ctlDvCd": "",
                "lang": "",
            },
        )
        self._api.check(payload)
        return RefundFee.from_response(payload)

    def refund(self, ticket: Ticket) -> None:
        """발권된 승차권을 환불합니다.

        Raises:
            KorailError: 환불이 거부됐습니다.
        """
        payload = self._api.post(
            API_ENDPOINTS["refund"],
            data={
                **self._api.base_payload(),
                "txtPrnNo": ticket.pnr_no,
                "h_orgtk_sale_dt": ticket.sale_info2,
                "h_orgtk_sale_wct_no": ticket.sale_info1,
                "h_orgtk_sale_sqno": ticket.sale_info3,
                "h_orgtk_ret_pwd": ticket.sale_info4,
                "h_mlg_stl": "N",
                "tk_ret_tms_dv_cd": "21",
                "trnNo": ticket.train.train_no,
                "pbpAcepTgtFlg": "N",
                "latitude": "",
                "longitude": "",
            },
        )
        self._api.check(payload)

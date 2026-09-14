"""발권 완료된 승차권."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pykorail.models.parsing import integer, text
from pykorail.models.schedule import Train

#: ``MyTicketList`` 응답의 ``reservation_list`` 항목 안에서 ``train_info`` 까지 가는 경로.
#: 각 단계가 리스트이고 첫 항목만 씁니다 — 앱도 그렇게 읽습니다.
TRAIN_INFO_PATH = ("ticket_list", "train_info")


def train_info_of(entry: dict[str, Any]) -> dict[str, Any] | None:
    """``reservation_list`` 항목 하나에서 ``train_info`` dict 를 꺼냅니다. 못 찾으면 ``None``.

    중간 단계가 빠지거나 빈 리스트로 오면 ``None`` 을 돌려줍니다. 날 인덱싱
    (``entry["ticket_list"][0]["train_info"][0]``)은 응답이 조금만 달라져도
    ``KeyError``/``IndexError`` 로 죽는데, 코레일은 필드를 빼먹고 보내는 서버라
    승차권 한 항목 때문에 목록 전체가 터지면 안 됩니다.

    **빈 dict 도 읽을 수 없는 항목으로 봅니다.** 구조만 있고 내용이 없으면
    승차권번호도 좌석도 금액도 없는 유령 승차권이 만들어져 목록에 섞입니다 —
    관용적으로 읽는 것과 없는 것을 지어내는 것은 다릅니다.
    """
    node: Any = entry
    for key in TRAIN_INFO_PATH:
        branch = node.get(key) if isinstance(node, dict) else None
        if not isinstance(branch, list) or not branch:
            return None
        node = branch[0]
    return node if isinstance(node, dict) and node else None


@dataclass(frozen=True)
class Ticket:
    """결제까지 끝난 승차권.

    승차권은 열차가 *아니라* 열차를 **참조**합니다 — ``ticket.train.dep_name`` 처럼
    쓰세요. 상속으로 묶으면 ``ticket.has_seat()`` 같은 의미 없는 연산이 딸려 옵니다
    (이미 발권됐으니 좌석 가용 여부를 물을 일이 없습니다).
    """

    train: Train
    seat_no: str
    seat_no_end: str | None
    seat_no_count: int
    car_no: str
    buyer_name: str
    sale_date: str
    pnr_no: str
    price: int

    # 환불 요청에 그대로 되돌려 줘야 하는 원권(原券) 식별자 4종.
    sale_info1: str
    sale_info2: str
    sale_info3: str
    sale_info4: str

    @classmethod
    def from_response(cls, data: dict[str, Any], *, seat_no: str | None = None) -> Ticket:
        """``train_info`` 항목 하나로 승차권을 만듭니다.

        Args:
            data: 승차권 상세가 담긴 ``train_info`` 항목.
            seat_no: 좌석 상세 조회로 확인한 실제 좌석번호. 넘기면 목록 응답의
                값을 덮고 ``seat_no_end`` 는 비웁니다(단일 좌석으로 확정되므로).
        """
        resolved_seat = text(data, "h_seat_no") if seat_no is None else seat_no
        return cls(
            train=Train.from_response(data),
            seat_no=resolved_seat,
            seat_no_end=text(data, "h_seat_no_end") if seat_no is None else None,
            seat_no_count=integer(data, "h_seat_cnt"),
            car_no=text(data, "h_srcar_no"),
            buyer_name=text(data, "h_buy_ps_nm"),
            sale_date=text(data, "h_orgtk_sale_dt"),
            pnr_no=text(data, "h_pnr_no"),
            price=integer(data, "h_rcvd_amt"),
            sale_info1=text(data, "h_orgtk_wct_no"),
            sale_info2=text(data, "h_orgtk_ret_sale_dt"),
            sale_info3=text(data, "h_orgtk_sale_sqno"),
            sale_info4=text(data, "h_orgtk_ret_pwd"),
        )

    @classmethod
    def from_ticket_list(cls, entry: dict[str, Any], *, seat_no: str | None = None) -> Ticket | None:
        """``MyTicketList`` 응답의 ``reservation_list`` 항목 하나를 풀어 승차권을 만듭니다.

        항목에서 ``train_info`` 를 찾지 못하면 ``None`` 입니다 — 읽을 것이 없는
        항목은 예외가 아니라 건너뛸 대상입니다.
        """
        raw = train_info_of(entry)
        return None if raw is None else cls.from_response(raw, seat_no=seat_no)

    @property
    def ticket_no(self) -> str:
        """원권 식별자 4종을 하이픈으로 이은 승차권 번호."""
        return "-".join((self.sale_info1, self.sale_info2, self.sale_info3, self.sale_info4))

    def __repr__(self) -> str:
        seats = (
            self.seat_no
            if self.seat_no_count == 1 or self.seat_no_end is None
            else f"{self.seat_no}~{self.seat_no_end}"
        )
        return f"{self.train.summary()} => {self.car_no}호 {seats}, {self.price}원"

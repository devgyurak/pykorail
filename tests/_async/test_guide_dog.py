"""안내견 동반 승객 — 조회 칸 합산 · 예매 블록 · 그리고 제약을 두지 않음.

안내견은 유형 코드가 어른과 같지만 조회에서는 어른 칸(``txtPsgFlg_1``)에 더해지고
예매에서는 할인 코드(``173``)가 달라 별도 블록으로 나갑니다. 여기서 그 계약과,
pykorail 이 앱의 인원 제약(안내견 ≤ 중증 · 경증 장애인)을 흉내 내지 않는다는 사실을
함께 고정합니다 — 누가 실수로 검사를 넣으면 이 테스트가 잡습니다.
"""

from __future__ import annotations

import pytest

from pykorail.models import (
    AdultPassenger,
    Disability1To3Passenger,
    Disability4To6Passenger,
    GuideDogPassenger,
)
from tests.payloads import (
    RESERVATION_LIST_PAYLOAD,
    RESERVE_OK,
    SEAT_CARS_PAYLOAD,
    SEAT_DETAIL_PAYLOAD,
    SEAT_MAP_PAYLOAD,
    SEATABLE_SEARCH_PAYLOAD,
    STATION_PAYLOAD,
)

#: 좌석 지정 예매까지 돌리는 라우트.
SEAT_ROUTES = {
    "stationdata": STATION_PAYLOAD,
    "search_schedule": SEATABLE_SEARCH_PAYLOAD,
    "seat_cars": SEAT_CARS_PAYLOAD,
    "seat_map": SEAT_MAP_PAYLOAD,
    "reserve": RESERVE_OK,
    "myreservationview": RESERVATION_LIST_PAYLOAD,
    "myreservationlist": SEAT_DETAIL_PAYLOAD,
}

#: 어느 유형도 세지 않은 조회 칸. 케이스마다 달라지는 칸만 덮어씁니다.
NO_FLAGS = {"txtPsgFlg_1": 0, "txtPsgFlg_2": 0, "txtPsgFlg_3": 0, "txtPsgFlg_4": 0, "txtPsgFlg_5": 0}


def flags_of(params: dict[str, object]) -> dict[str, object]:
    """조회 폼의 인원 칸 다섯 개."""
    return {f"txtPsgFlg_{index}": params[f"txtPsgFlg_{index}"] for index in range(1, 6)}


@pytest.fixture
async def seated(make_korail):
    """로그인한 클라이언트, 가짜 세션, 조회한 열차, 그 열차 첫 호차의 좌석들."""
    client, session = make_korail(SEAT_ROUTES)
    train = (await client.trains.search("서울", "부산"))[0]
    seats = await client.trains.seats(train, (await client.trains.cars(train))[0])
    return client, session, train, seats


class TestSearchFlags:
    @pytest.mark.parametrize(
        ("passengers", "expected"),
        [
            ([AdultPassenger(1), GuideDogPassenger(1)], {**NO_FLAGS, "txtPsgFlg_1": 2}),
            ([Disability1To3Passenger(1), GuideDogPassenger(1)], {**NO_FLAGS, "txtPsgFlg_1": 1, "txtPsgFlg_4": 1}),
            ([Disability4To6Passenger(1), GuideDogPassenger(1)], {**NO_FLAGS, "txtPsgFlg_1": 1, "txtPsgFlg_5": 1}),
        ],
        ids=["어른+안내견", "중증+안내견", "경증+안내견"],
    )
    async def test_guide_dog_is_added_to_the_adult_flag(self, korail, passengers, expected) -> None:
        # given
        client, session = korail

        # when
        await client.trains.search("서울", "부산", passengers=passengers)

        # then
        assert flags_of(session.kwargs_for("search_schedule")["params"]) == expected

    async def test_guide_dog_alone_still_searches(self, korail) -> None:
        """앱은 장애인 없이 안내견만 고를 수 없게 막지만, pykorail 은 막지 않습니다."""
        # given
        client, session = korail

        # when
        await client.trains.search("서울", "부산", passengers=[GuideDogPassenger(1)])

        # then
        assert flags_of(session.kwargs_for("search_schedule")["params"])["txtPsgFlg_1"] == 1

    async def test_more_guide_dogs_than_disabled_still_searches(self, korail) -> None:
        """앱의 인원 제약을 클라이언트에서 흉내 내지 않습니다."""
        # given
        client, session = korail

        # when
        await client.trains.search("서울", "부산", passengers=[Disability1To3Passenger(1), GuideDogPassenger(2)])

        # then
        params = session.kwargs_for("search_schedule")["params"]
        assert (params["txtPsgFlg_1"], params["txtPsgFlg_4"]) == (2, 1)


class TestReservationBlocks:
    async def test_create_sends_a_guide_dog_block(self, korail) -> None:
        # given
        client, session = korail
        train = (await client.trains.search("서울", "부산"))[0]

        # when
        await client.reservations.create(train, passengers=[Disability1To3Passenger(1), GuideDogPassenger(1)])

        # then
        params = session.kwargs_for("reserve")["params"]
        assert (params["txtCompaCnt1"], params["txtPsgTpCd1"], params["txtDiscKndCd1"]) == (1, "1", "111")
        assert (params["txtCompaCnt2"], params["txtPsgTpCd2"], params["txtDiscKndCd2"]) == (1, "1", "173")
        assert params["txtTotPsgCnt"] == 2

    async def test_create_counts_the_guide_dog_in_the_total(self, korail) -> None:
        # given
        client, session = korail
        train = (await client.trains.search("서울", "부산"))[0]

        # when
        await client.reservations.create(train, passengers=[GuideDogPassenger(1)])

        # then
        params = session.kwargs_for("reserve")["params"]
        assert params["txtDiscKndCd1"] == "173"
        assert params["txtTotPsgCnt"] == 1


class TestSeatDesignatedReservation:
    async def test_guide_dog_counts_as_a_passenger_for_seats(self, seated) -> None:
        # given
        client, session, train, seats = seated

        # when
        await client.reservations.create_with_seats(
            train, seats[:2], [Disability1To3Passenger(1), GuideDogPassenger(1)]
        )

        # then
        data = session.kwargs_for("reserve")["data"]
        assert data["txtTotPsgCnt"] == "2"
        assert (data["txtPsgTpCd2"], data["txtDiscKndCd2"]) == ("1", "173")

    async def test_guide_dog_is_counted_in_the_required_seat_count(self, seated) -> None:
        """안내견도 한 명으로 세므로 좌석이 모자라면 요청 전에 멈춥니다."""
        # given
        client, session, train, seats = seated

        # when
        with pytest.raises(ValueError, match="좌석 1개, 승객 2명"):
            await client.reservations.create_with_seats(
                train, seats[:1], [Disability1To3Passenger(1), GuideDogPassenger(1)]
            )

        # then
        assert session.all_kwargs_for("reserve") == []

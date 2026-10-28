"""승객 합치기와 폼 직렬화."""

from __future__ import annotations

import dataclasses
from typing import cast

import pytest

from pykorail.models import (
    AdultPassenger,
    ChildPassenger,
    Disability1To3Passenger,
    GuideDogPassenger,
    Passenger,
    SeniorPassenger,
    ToddlerPassenger,
)


def counts(passengers: list[Passenger]) -> list[tuple[str, int]]:
    return sorted((type(p).__name__, p.count) for p in passengers)


class TestDefaults:
    @pytest.mark.parametrize(
        ("passenger_type", "type_code", "discount"),
        [
            (AdultPassenger, "1", "000"),
            (ChildPassenger, "3", "000"),
            (ToddlerPassenger, "3", "321"),
            (SeniorPassenger, "1", "131"),
            (Disability1To3Passenger, "1", "111"),
            (GuideDogPassenger, "1", "173"),
        ],
    )
    def test_type_and_discount_codes(self, passenger_type: type[Passenger], type_code: str, discount: str) -> None:
        # when
        passenger = passenger_type()

        # then
        assert passenger.typecode == type_code
        assert passenger.discount_type == discount

    def test_discount_can_be_overridden(self) -> None:
        # when
        passenger = AdultPassenger(discount_type="131")

        # then
        assert passenger.discount_type == "131"


class TestReduce:
    def test_merges_same_type(self) -> None:
        # given
        passengers = [AdultPassenger(1), AdultPassenger(2)]

        # when
        merged = Passenger.reduce(passengers)

        # then
        assert counts(merged) == [("AdultPassenger", 3)]

    def test_merges_across_non_adjacent_entries(self) -> None:
        """groupby 는 연속된 키만 묶으므로 정렬이 빠지면 어른이 두 블록으로 나갑니다."""
        # given
        passengers = [AdultPassenger(1), ChildPassenger(1), AdultPassenger(1)]

        # when
        merged = Passenger.reduce(passengers)

        # then
        assert counts(merged) == [("AdultPassenger", 2), ("ChildPassenger", 1)]

    def test_keeps_different_discounts_apart(self) -> None:
        """유아와 어린이는 유형 코드가 같지만 할인 코드가 달라 합쳐지면 안 됩니다."""
        # given
        passengers = [ChildPassenger(1), ToddlerPassenger(1)]

        # when
        merged = Passenger.reduce(passengers)

        # then
        assert counts(merged) == [("ChildPassenger", 1), ("ToddlerPassenger", 1)]

    def test_keeps_guide_dog_and_adult_apart(self) -> None:
        """안내견과 어른도 유형 코드(`1`)는 같지만 할인 코드가 달라 합쳐지면 안 됩니다."""
        # given
        passengers = [AdultPassenger(1), GuideDogPassenger(1)]

        # when
        merged = Passenger.reduce(passengers)

        # then
        assert counts(merged) == [("AdultPassenger", 1), ("GuideDogPassenger", 1)]

    def test_keeps_different_cards_apart(self) -> None:
        # given
        passengers = [AdultPassenger(1, card="A"), AdultPassenger(1, card="B")]

        # when
        merged = Passenger.reduce(passengers)

        # then
        assert len(merged) == 2

    def test_drops_zero_counts(self) -> None:
        # given
        passengers = [AdultPassenger(0), ChildPassenger(2)]

        # when
        merged = Passenger.reduce(passengers)

        # then
        assert counts(merged) == [("ChildPassenger", 2)]

    def test_empty_input(self) -> None:
        # when
        merged = Passenger.reduce([])

        # then
        assert merged == []

    def test_rejects_non_passengers(self) -> None:
        # given: 정적으로는 막히지만 런타임 가드도 살아 있어야 합니다.
        not_passengers = cast("list[Passenger]", ["adult"])

        # when & then
        with pytest.raises(TypeError):
            Passenger.reduce(not_passengers)


class TestAdd:
    def test_preserves_card_details(self) -> None:
        # given
        first = AdultPassenger(1, card="C", card_no="123", card_pw="45")
        second = AdultPassenger(2, card="C", card_no="123", card_pw="45")

        # when
        merged = first + second

        # then
        assert merged.count == 3
        assert (merged.card, merged.card_no, merged.card_pw) == ("C", "123", "45")

    def test_rejects_different_types(self) -> None:
        # when & then
        with pytest.raises(TypeError, match="different passenger types"):
            AdultPassenger(1) + ChildPassenger(1)  # type: ignore[operator]

    def test_rejects_different_group_keys(self) -> None:
        # when & then
        with pytest.raises(TypeError, match="different group keys"):
            AdultPassenger(1, card="A") + AdultPassenger(1, card="B")

    def test_group_key_error_hides_card_details(self) -> None:
        # given
        first = AdultPassenger(1, card="A", card_no="1234567812345678", card_pw="9012")
        second = AdultPassenger(1, card="B", card_no="8765432187654321", card_pw="3456")

        # when
        with pytest.raises(TypeError) as raised:
            first + second

        # then
        assert [s for s in ("1234567812345678", "9012", "8765432187654321", "3456") if s in str(raised.value)] == []


class TestFormSerialization:
    def test_get_dict_uses_index(self) -> None:
        # given
        passenger = AdultPassenger(2)

        # when
        fields = passenger.get_dict(1)

        # then
        assert fields == {
            "txtPsgTpCd1": "1",
            "txtDiscKndCd1": "000",
            "txtCompaCnt1": 2,
            "txtCardCode_1": "",
            "txtCardNo_1": "",
            "txtCardPw_1": "",
        }

    def test_indices_do_not_collide(self) -> None:
        # when
        first = AdultPassenger(1).get_dict(1)
        second = ChildPassenger(1).get_dict(2)

        # then
        assert not set(first) & set(second)


class TestValueObject:
    def test_rejects_a_negative_count(self) -> None:
        # when & then
        with pytest.raises(ValueError, match="must not be negative"):
            AdultPassenger(-1)

    def test_allows_a_zero_count(self) -> None:
        # when
        passenger = AdultPassenger(0)

        # then
        assert passenger.count == 0

    def test_is_immutable(self) -> None:
        # given
        passenger = AdultPassenger(1)

        # when & then
        with pytest.raises(dataclasses.FrozenInstanceError):
            passenger.count = 2  # ty: ignore[invalid-assignment]  # 불변 검사가 목적이라 타입 검사기의 경고를 억제합니다

    def test_equal_by_type_and_value(self) -> None:
        # when & then
        assert AdultPassenger(2) == AdultPassenger(2)
        assert AdultPassenger(2) != AdultPassenger(1)

    def test_different_types_are_never_equal(self) -> None:
        # when & then
        assert AdultPassenger(1) != ChildPassenger(1)

    def test_repr_hides_card_details(self) -> None:
        # given
        passenger = AdultPassenger(1, card="A", card_no="1234567812345678", card_pw="9012")

        # when
        rendered = repr(passenger)

        # then
        assert [secret for secret in ("1234567812345678", "9012") if secret in rendered] == []

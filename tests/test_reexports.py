"""기존 import 경로가 그대로 살아 있는지 지킵니다.

``_sync`` 는 생성물이라, 공개 경로(``pykorail.client`` · ``pykorail.resources.*``)가
그것을 재수출하고 있다는 사실이 곧 하위 호환입니다. 재수출이 끊기면 여기서 먼저
드러납니다.
"""

from __future__ import annotations

import importlib

import pytest

import pykorail._async.api
import pykorail.api
import pykorail.client
import pykorail.resources
import pykorail.resources.airport_bus
import pykorail.resources.base
import pykorail.resources.clock
import pykorail.resources.membership
import pykorail.resources.reservations
import pykorail.resources.stations
import pykorail.resources.tickets
import pykorail.resources.trains
from pykorail._shared import ACCESS_RESTRICTED_CODE, KST, Account, to_kst, without_blanks
from pykorail._sync.api import ApiClient as SyncApiClient
from pykorail._sync.client import Korail as SyncKorail
from pykorail._sync.resources import Resource as SyncResource
from pykorail._sync.resources import trains as sync_trains
from pykorail._sync.resources.airport_bus import AirportBusResource as SyncAirportBusResource
from pykorail._sync.resources.base import Resource as SyncBaseResource
from pykorail._sync.resources.membership import MembershipResource as SyncMembershipResource
from pykorail._sync.resources.reservations import ReservationResource as SyncReservationResource
from pykorail._sync.resources.stations import StationResource as SyncStationResource
from pykorail._sync.resources.tickets import TicketResource as SyncTicketResource
from pykorail._sync.resources.trains import TrainResource as SyncTrainResource

#: develop(v0.3.x) 시점에 각 모듈이 모듈 속성으로 노출하던 이름의 스냅숏입니다.
#: I/O 계층을 ``_async``/``_sync`` 로 가르면서 이 이름들이 조용히 사라진 적이 있어
#: (``pykorail.client.create_session`` · ``pykorail.api.ACCESS_RESTRICTED_CODE`` ·
#: ``pykorail.resources.membership.DEFAULT_PERIOD``), 다시는 빠지지 않게 고정합니다.
#: 표준 라이브러리·typing 에서 온 이름(``Any`` · ``json`` 등)은 공개 표면이 아니라 뺐습니다.
DEVELOP_PUBLIC_NAMES = {
    "pykorail.client": [
        "API_ENDPOINTS",
        "API_KEY",
        "APP_DISPLAY_VERSION",
        "APP_VERSION",
        "AirportBusResource",
        "ApiClient",
        "DEFAULT_HEADERS",
        "DEVICE",
        "EMAIL_REGEX",
        "HYPHENLESS_PHONE_REGEX",
        "Korail",
        "LoginFailedError",
        "MembershipResource",
        "PHONE_NUMBER_REGEX",
        "PasswordChangeRequiredError",
        "RequestSigner",
        "ReservationResource",
        "StationResource",
        "TicketResource",
        "TrainResource",
        "create_session",
        "encrypt_password",
        "validate_android_id",
    ],
    "pykorail.api": [
        "ACCESS_RESTRICTED_CODE",
        "API_KEY",
        "APP_DISPLAY_VERSION",
        "APP_VERSION",
        "AccessRestrictedError",
        "Account",
        "ApiClient",
        "DEVICE",
        "HttpStatusError",
        "TransportError",
        "error_for_code",
        "logger",
        "text",
    ],
    "pykorail.resources": [
        "AirportBusResource",
        "MembershipResource",
        "ReservationResource",
        "Resource",
        "StationResource",
        "TicketResource",
        "TrainResource",
        "to_kst",
    ],
    "pykorail.resources.stations": [
        "API_ENDPOINTS",
        "Resource",
        "Station",
        "StationNotFoundError",
        "StationResource",
        "parse_stations",
    ],
    "pykorail.resources.trains": [
        "API_ENDPOINTS",
        "APP_VERSION",
        "AdultPassenger",
        "Car",
        "CarSeat",
        "ChildPassenger",
        "DEVICE",
        "Disability1To3Passenger",
        "Disability4To6Passenger",
        "Fare",
        "KST",
        "MAX_PAGES",
        "NoResultsError",
        "PAST_TOLERANCE",
        "Passenger",
        "PastDepartureError",
        "Resource",
        "SeatClass",
        "SeniorPassenger",
        "ToddlerPassenger",
        "Train",
        "TrainResource",
        "TrainType",
        "Transfer",
        "TransferStation",
        "parse_transfers",
        "records",
        "to_kst",
        "without_blanks",
    ],
    "pykorail.resources.tickets": [
        "API_ENDPOINTS",
        "NoResultsError",
        "RefundFee",
        "Resource",
        "Ticket",
        "TicketResource",
        "records",
        "train_info_of",
    ],
    "pykorail.resources.reservations": [
        "API_ENDPOINTS",
        "AdultPassenger",
        "CarSeat",
        "Card",
        "KorailError",
        "NoResultsError",
        "Passenger",
        "Reservation",
        "ReservationResource",
        "ReserveOption",
        "Resource",
        "Seat",
        "SeatClass",
        "Transfer",
        "records",
        "text",
        "without_blanks",
    ],
    "pykorail.resources.membership": [
        "API_ENDPOINTS",
        "Coupon",
        "DEFAULT_PERIOD",
        "MembershipResource",
        "Mileage",
        "MileageInquiry",
        "MileageType",
        "NoResultsError",
        "Resource",
        "records",
        "to_kst",
    ],
    "pykorail.resources.airport_bus": [
        "API_ENDPOINTS",
        "AdultPassenger",
        "AirportBus",
        "AirportBusResource",
        "BusStop",
        "CarSeat",
        "NoResultsError",
        "Passenger",
        "Resource",
        "StationNotFoundError",
        "parse_bus_stops",
        "records",
        "text",
        "to_kst",
    ],
    "pykorail.resources.base": ["Resource", "without_blanks"],
    "pykorail.resources.clock": ["KST", "KST_OFFSET_HOURS", "to_kst"],
}


def test_client_reexports_the_generated_sync_class() -> None:
    # when & then
    assert pykorail.client.Korail is SyncKorail


def test_api_reexports_the_generated_sync_class() -> None:
    # when & then
    assert pykorail.api.ApiClient is SyncApiClient


def test_api_and_async_share_the_same_account_class() -> None:
    """동기·비동기가 같은 로그인 상태 클래스를 써야 합니다 (#90 의 목적)."""
    # when & then
    assert pykorail.api.Account is pykorail._async.api.Account
    assert pykorail.api.Account is Account
    assert pykorail.api.ACCESS_RESTRICTED_CODE is ACCESS_RESTRICTED_CODE


def test_resource_package_reexports_the_generated_sync_classes() -> None:
    # when & then
    assert pykorail.resources.Resource is SyncResource
    assert pykorail.resources.StationResource is SyncStationResource
    assert pykorail.resources.TrainResource is SyncTrainResource
    assert pykorail.resources.ReservationResource is SyncReservationResource
    assert pykorail.resources.TicketResource is SyncTicketResource
    assert pykorail.resources.MembershipResource is SyncMembershipResource
    assert pykorail.resources.AirportBusResource is SyncAirportBusResource


def test_resource_modules_reexport_the_generated_sync_classes() -> None:
    # when & then
    assert pykorail.resources.base.Resource is SyncBaseResource
    assert pykorail.resources.stations.StationResource is SyncStationResource
    assert pykorail.resources.trains.TrainResource is SyncTrainResource
    assert pykorail.resources.reservations.ReservationResource is SyncReservationResource
    assert pykorail.resources.tickets.TicketResource is SyncTicketResource
    assert pykorail.resources.membership.MembershipResource is SyncMembershipResource
    assert pykorail.resources.airport_bus.AirportBusResource is SyncAirportBusResource


def test_shared_helpers_are_re_exposed_at_the_old_paths() -> None:
    # when & then
    assert pykorail.resources.base.without_blanks is without_blanks
    assert pykorail.resources.clock.to_kst is to_kst
    assert pykorail.resources.clock.KST is KST
    assert pykorail.resources.trains.to_kst is sync_trains.to_kst
    assert pykorail.resources.trains.KST is sync_trains.KST
    assert pykorail.resources.trains.MAX_PAGES == sync_trains.MAX_PAGES
    assert pykorail.resources.trains.PAST_TOLERANCE == sync_trains.PAST_TOLERANCE


@pytest.mark.parametrize("module_name", sorted(DEVELOP_PUBLIC_NAMES), ids=lambda name: name.removeprefix("pykorail."))
def test_develop_public_names_stay_reachable(module_name: str) -> None:
    """리팩터링 전에 접근되던 이름이 옛 경로로 계속 접근돼야 합니다."""
    # given
    module = importlib.import_module(module_name)

    # when
    missing = [name for name in DEVELOP_PUBLIC_NAMES[module_name] if not hasattr(module, name)]

    # then
    assert missing == []


def test_api_logger_keeps_its_name() -> None:
    """``verbose`` 로그를 ``pykorail.api`` 로거에 걸어 둔 사용자가 계속 받아야 합니다."""
    # when & then
    assert pykorail.api.logger.name == "pykorail.api"


def test_async_logger_has_its_own_name() -> None:
    """비동기 호출은 동기 로거를 덮지 않고 별도 이름으로 나갑니다."""
    # when & then
    assert pykorail._async.api.logger.name == "pykorail.api.async"


def test_async_classes_are_reachable_from_the_public_packages() -> None:
    """타입 힌트를 달려고 private 경로(``pykorail._async...``)를 쓰지 않아도 돼야 합니다."""
    # when & then
    assert pykorail.api.AsyncApiClient.__name__ == "AsyncApiClient"
    assert pykorail.resources.AsyncResource.__name__ == "AsyncResource"
    assert pykorail.resources.AsyncStationResource.__name__ == "AsyncStationResource"
    assert pykorail.resources.AsyncTrainResource.__name__ == "AsyncTrainResource"
    assert pykorail.resources.AsyncReservationResource.__name__ == "AsyncReservationResource"
    assert pykorail.resources.AsyncTicketResource.__name__ == "AsyncTicketResource"
    assert pykorail.resources.AsyncMembershipResource.__name__ == "AsyncMembershipResource"
    assert pykorail.resources.AsyncAirportBusResource.__name__ == "AsyncAirportBusResource"

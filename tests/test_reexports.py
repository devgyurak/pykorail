"""기존 import 경로가 그대로 살아 있는지 지킵니다.

``_sync`` 는 생성물이라, 공개 경로(``pykorail.client`` · ``pykorail.resources.*``)가
그것을 재수출하고 있다는 사실이 곧 하위 호환입니다. 재수출이 끊기면 여기서 먼저
드러납니다.
"""

from __future__ import annotations

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
from pykorail._shared import KST, to_kst, without_blanks
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


def test_client_reexports_the_generated_sync_class() -> None:
    # when & then
    assert pykorail.client.Korail is SyncKorail


def test_api_reexports_the_generated_sync_class() -> None:
    # when & then
    assert pykorail.api.ApiClient is SyncApiClient


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

"""역 마스터 리소스."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pykorail._async.resources.base import AsyncResource
from pykorail.constants import API_ENDPOINTS
from pykorail.exceptions import StationNotFoundError
from pykorail.models.station import Station, parse_stations

if TYPE_CHECKING:
    from pykorail._async.api import AsyncApiClient


class AsyncStationResource(AsyncResource):
    """``korail.stations`` — 역 조회와 이름 검증."""

    def __init__(self, api: AsyncApiClient) -> None:
        super().__init__(api)
        self._cache: list[Station] | None = None
        self._names: set[str] = set()

    async def all(self, refresh: bool = False) -> list[Station]:
        """역 마스터 전체 (``com.korail.mobile.common.stationdata``).

        앱과 동일하게 파라미터 없는 bodyless POST 로 호출합니다. 로그인·서명이
        필요 없는 공개 조회라 로그인 전에도 부를 수 있습니다.

        역 목록은 거의 바뀌지 않고 이름 검증에도 쓰이므로 **리소스 수명 동안
        캐시**합니다. 새로 받아오려면 ``refresh=True``.
        """
        if refresh or self._cache is None:
            self._cache = parse_stations(await self._api.post(API_ENDPOINTS["stationdata"]))
            self._names = {station.name for station in self._cache}
        # 호출부가 리스트를 건드려도 캐시가 깨지지 않도록 복사본을 줍니다.
        return list(self._cache)

    async def names(self) -> set[str]:
        """역 이름 집합 (캐시 사용)."""
        await self.all()
        return set(self._names)

    async def find(self, name: str) -> Station | None:
        """이름이 정확히 일치하는 역. 없으면 ``None``."""
        return next((station for station in await self.all() if station.name == name), None)

    async def ensure_exist(self, *names: str) -> None:
        """역 마스터에 없는 이름이면 조회를 보내기 전에 막습니다.

        서버는 없는 역에도 그냥 빈 결과를 주기 때문에, 오타와 "그 시간대에 열차가
        없음"이 구분되지 않습니다. 여기서 갈라 놓습니다.

        Raises:
            StationNotFoundError: 하나라도 역 마스터에 없습니다.
        """
        await self.all()  # 캐시 채우기
        unknown = [name for name in names if name not in self._names]
        if unknown:
            raise StationNotFoundError(unknown, self._names)

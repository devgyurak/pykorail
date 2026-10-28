# API 레퍼런스

pykorail 의 전체 API 표면입니다. 처음이라면 [README](../README.md) 의 예제부터 보세요.

이 문서는 `tests/test_readme.py` 가 소스와 대조합니다 — 메서드·필드·코드값이
어긋나면 테스트가 실패하므로, 코드를 바꿨다면 여기도 함께 고쳐야 합니다.

---

## 클라이언트

### `Korail`

```python
Korail(
    verbose: bool = False,
    device_profile: DeviceProfileLike | None = None,
    validate_stations: bool = True,
    *,
    android_id: str | None = None,
    dynapath_engine: DynaPathEngine | None = None,
)
```

| 인자 | 설명 |
| --- | --- |
| `verbose` | 요청·응답 본문을 `DEBUG` 로그로 남깁니다. **개인정보가 찍히니 운영에서 켜지 마세요.** |
| `device_profile` | DynaPath의 ID·모델·OS를 지정합니다. UA는 `korailtalk`으로 고정됩니다. [기기 프로파일](#기기-프로파일) 참조. |
| `android_id` | 저장한 ID를 복원합니다. 프로파일에도 ID가 있으면 같은 값이어야 하며, 형식 오류·충돌 시 세션 생성 전에 `ValueError`가 납니다. |
| `validate_stations` | `trains.search` 전에 역 이름을 검증합니다. 끄면 역 마스터 조회 1회를 아낍니다. |
| `dynapath_engine` | DynaPath 토큰을 만드는 엔진입니다. 기본은 `DeclarationDynaPathEngine`(프로파일이 있으면 `from_profile`). 실기기 `board`·attestation 값이 필요하면 `DynaPathEngine` 계약을 만족하는 엔진을 넘기세요. [기기 프로파일](#기기-프로파일) 참조. |

| 메서드 · 속성 | 반환 | 설명 |
| --- | --- | --- |
| `Korail.logged_in(id, pw, *, verbose=False, device_profile=None, validate_stations=True, android_id=None, dynapath_engine=None)` | `Korail` | 생성 + 로그인. ID 검증 오류는 `ValueError`, 로그인 실패는 `LoginFailedError`입니다. |
| `android_id` | `str` | 실제 서명에 사용하는 ID. 프로파일이 없어도 저장할 수 있는 읽기 전용 속성입니다. |
| `login(korail_id, korail_pw)` | `None` | 실패는 전부 `LoginFailedError`. 성공 여부를 반환하지 않습니다. 비밀번호 변경 안내에 걸린 계정은 그 하위 타입 [`PasswordChangeRequiredError`](#예외). |
| `logout()` | `None` | **서버 세션만** 끊습니다. HTTP 연결은 살아 있어 재로그인할 수 있습니다. |
| `close()` | `None` | HTTP 연결 정리. `with` 문이 자동 호출합니다. |
| `is_logged_in` | `bool` | 로그인 상태. (옛 이름 `logined` 는 0.7.0 에서 지웁니다) |
| `membership_number` · `name` · `email` · `phone_number` | `str \| None` | 로그인 후 채워집니다. |

`korail_id` 는 형태로 자동 판별합니다 — 이메일 · 휴대폰(`010-1234-5678`) · 회원번호.

> [!NOTE]
> `logout()` 과 `close()` 는 다릅니다. 로그아웃은 프로토콜 상태, 연결은 자원이라
> 수명이 다릅니다. 계정을 바꿔 다시 로그인하려면 연결이 살아 있어야 합니다.

> [!NOTE]
> **v0.4.0 부터** I/O 계층이 원본(`src/pykorail/_async`)과 생성물
> (`src/pykorail/_sync`)로 갈라졌습니다. 공개 경로와 서버로 나가는 요청은 그대로지만,
> `pykorail.client.create_session` 처럼 **하위 모듈의 내부 이름을 monkeypatch 하던
> 방식**은 더 이상 실제 클라이언트에 영향을 주지 않습니다(이름 자체는 옛 경로로
> 계속 접근됩니다). 그런 이름들은 공개 API 가 아니었지만, 동작이 달라진 점은 적어
> 둡니다.

### `AsyncKorail`

같은 API 를 `await` 로 쓰는 클라이언트입니다. 생성자 인자와 리소스(`stations` ·
`trains` · `reservations` · `tickets` · `membership` · `airport_bus`)는
[`Korail`](#korail) 과 같고, I/O 가 닿는 메서드만 코루틴입니다.

타입 힌트에는 `pykorail.resources.AsyncStationResource` 처럼 ``Async*Resource`` 를,
API 클라이언트는 `pykorail.api.AsyncApiClient` 를 씁니다.

```python
import asyncio

from pykorail import AsyncKorail


async def main() -> None:
    async with await AsyncKorail.logged_in("me@example.com", "password") as korail:
        trains = await korail.trains.search("서울", "부산")
        print(trains[0])


asyncio.run(main())
```

`await` 가 붙는 것: `AsyncKorail` 의 `logged_in` · `login` · `logout` · `close` 와 리소스의
조회·예매 메서드 전부(`all` · `find` · `search` · `cars` · `seats` · `create` · `pay`
· `cancel` · `refund` · `mileage` · `coupons` · `stops` …). 컨텍스트 관리자는
`async with await …` 입니다.

**제약**

- **asyncio 전용입니다.** `curl_cffi` 의 비동기 세션이 asyncio 만 지원하므로 trio 는
  지원하지 않습니다.
- **인스턴스 하나는 이벤트 루프 하나에서만** 쓰세요. 로그인 상태를 태스크들이
  공유합니다. 생성자는 네트워크를 치지 않으므로 루프 밖에서도 됩니다.
- **동시에 `login` 을 부르는 것은 지원하지 않습니다.**
- **`requests` 폴백이 없습니다.** `curl_cffi` 를 못 쓰면 `AsyncKorail()` 이
  [`TransportError`](#예외) 로 안내합니다.
- **요청 순서는 앱과 같습니다.** `reservations.all()` 처럼 예약마다 상세를 조회하는
  흐름을 `gather` 로 묶지 않았습니다.
- **첫 캐시 조회 전에 여러 코루틴으로** `stations.all()` · `airport_bus.stops()` 를
  동시에 부르면 역·정류장 목록을 중복 조회할 수 있습니다. 캐시가 채워진 뒤에는
  한 번만 나갑니다. (lock 을 걸면 생성되는 동기 코드와 갈라져 이번 판에는 넣지
  않았습니다. 필요하면 직접 한 번 조회해 캐시를 채운 뒤 동시 호출을 시작하세요.)

### `korail.stations`

로그인 없이 호출할 수 있는 공개 조회입니다. 결과는 **클라이언트 수명 동안 캐시**되고,
역 이름 검증에도 쓰입니다.

| 메서드 | 반환 | 설명 |
| --- | --- | --- |
| `all(refresh=False)` | `list[Station]` | 역 마스터 전체 (2026-09 기준 **281개**). `refresh=True` 로 다시 받습니다. |
| `find(name)` | `Station \| None` | 이름이 정확히 일치하는 역. |
| `names()` | `set[str]` | 역 이름 집합. |
| `ensure_exist(*names)` | `None` | 없으면 `StationNotFoundError`. `search` 가 내부에서 호출합니다. |

```python
korail.stations.find("부산")  # 부산(0020)
[s.name for s in korail.stations.all() if s.is_major][:5]
# ['서울', '용산', '광명', '수서', '영등포']
```

주요역(`is_major`)은 45개이고 `major` 값이 앱에서의 노출 순서입니다.

### `korail.trains`

```python
search(
    dep: str,
    arr: str,
    depart_after: datetime | None = None,
    train_type: TrainTypeCode = TrainType.ALL,
    passengers: list[Passenger] | None = None,
    include_no_seats: bool = False,
    include_waiting_list: bool = False,
    include_nearby_stations: bool = False,
    max_pages: int = 1,
) -> list[Train]
```

| 인자 | 설명 |
| --- | --- |
| `dep` · `arr` | 역 **이름** (코드가 아닙니다). 존재하지 않으면 요청 전에 `StationNotFoundError`. |
| `depart_after` | 그날, 이 시각 **이후** 출발. tz 없으면 KST 로 해석, 있으면 KST 로 변환. 생략 시 현재. **이미 지난 시각이면 `PastDepartureError`.** |
| `train_type` | [`TrainType`](#traintype) 코드. 기본 `ALL`. |
| `passengers` | 생략 시 어른 1명. 인원수는 좌석 가용 판단에 영향을 줍니다. |
| `include_no_seats` | 매진 열차도 포함 — 사실상 **전부 보기**입니다. |
| `include_waiting_list` | 예약대기 가능 열차도 포함. |
| `include_nearby_stations` | **인근역** 출발·도착 열차도 함께 봅니다 (앱의 "인접역"). 아래 참고. |
| `max_pages` | 이어 받을 쪽 수의 상한. 기본 `1`. 서버는 요청 한 번에 한 쪽만 주므로, 2 이상이면 마지막 열차의 출발 시각부터 다시 조회해 이어 붙입니다. 새 열차가 없으면 상한 전에 멈춥니다. **쪽마다 요청이 한 번씩 더 나갑니다.** 1 – 20 을 벗어나면 `ValueError`. |

조건에 맞는 열차가 없으면 `NoResultsError` 를 던집니다 (빈 리스트가 아닙니다).

이미 지난 시각으로 조회하면 요청을 보내기 전에 `PastDepartureError` 가 납니다.
서버는 과거 시각에도 빈 결과만 주기 때문에 "이미 떠난 열차" 와 "그 시간대에 열차가
없음" 이 구분되지 않아서입니다. 계산 지연을 감안해 `PAST_TOLERANCE`(1분)만큼은
봐주므로, `datetime.now()` 를 그대로 넘겨도 됩니다.

```python
from pykorail import PastDepartureError

try:
    korail.trains.search("서울", "부산", depart_after=datetime(2020, 1, 1))
except PastDepartureError as exc:
    print(exc.requested, exc.now)  # 요청 시각과 판정 기준 시각 (둘 다 KST)
```

```python
from pykorail import TrainType

# KTX 만, 매진 포함해서 전부
trains = korail.trains.search("서울", "동대구", train_type=TrainType.KTX, include_no_seats=True)

# 예약대기라도 잡고 싶을 때
trains = korail.trains.search("서울", "부산", include_waiting_list=True)
```

#### 인근역 포함 조회

`include_nearby_stations=True` 는 앱의 **"인접역"** 옵션과 같습니다. 요청한 역만이
아니라 같은 권역의 인근역에서 출발하거나 인근역에 도착하는 열차까지 후보에 넣습니다.
용산 → 대전을 찾으면 서울 → 대전 · 용산 → 서대전 편이 함께 나옵니다.

```python
trains = korail.trains.search("용산", "대전", include_nearby_stations=True)

for train in trains:
    print(train.dep_name, train.arr_name)  # 서울 대전 / 용산 서대전 / 서울 서대전 …
```

어떤 역인지는 응답에 따로 표시되지 않습니다. `dep_name`·`arr_name` 이 **요청한 역과
다를 수 있다**는 것이 이 옵션의 전부이고, 열차 한 편의 모양은 그대로입니다.

서버에는 "출발역만 인근역 허용" 같은 세부 선택이 없습니다 — 플래그 하나로 출발·도착
양쪽이 함께 열립니다. 한쪽만 원한다면 결과에서 고르세요.

```python
from_yongsan = [t for t in trains if t.dep_name == "용산"]
```

> [!WARNING]
> 결과가 **더해지는 것이 아니라 후보가 넓어지는 것**입니다. 서버가 주는 한 페이지
> 안에서 인근역 편이 시간순으로 끼어들기 때문에, 켜면 원래 보이던 뒤쪽 직통편이
> 밀려날 수 있습니다. 기본값이 꺼짐인 이유입니다.

반대로 직통이 없는 구간은 이 옵션 없이는 조회할 방법이 없습니다. 용산 → 대전을 끄고
조회하면 서버가 `WRD000061`("직통열차는 없지만, 환승으로 조회 가능합니다")로 응답해
`NoResultsError` 가 됩니다. 켠다고 결과가 보장되는 것은 아니고 — 인근역 편도 없으면
그대로 `NoResultsError` 입니다 — 인근역 편이 있다면 그때 내려옵니다.

> [!TIP]
> `depart_after` 는 실행 머신의 로컬 타임존과 무관하게 항상 KST 로 해석됩니다.
> UTC 서버에서 돌려도 `09:00` 은 한국시간 오전 9시입니다.

#### 환승 조회

직통이 없는 구간은 한 번 갈아타는 여정으로 찾습니다. **로그인하지 않아도 됩니다.**

```python
search_transfers(
    dep: str,
    arr: str,
    depart_after: datetime | None = None,
    train_type: TrainTypeCode = TrainType.ALL,
    passengers: Sequence[Passenger] | None = None,
    include_no_seats: bool = False,
) -> list[Transfer]

transfer_stations(dep: str, arr: str) -> list[TransferStation]
```

| 인자 | 설명 |
| --- | --- |
| `dep` · `arr` · `depart_after` · `train_type` · `passengers` | `search` 와 같습니다. |
| `include_no_seats` | 한 구간이라도 매진인 여정까지 포함. 기본은 **두 구간 모두** 좌석이 있는 여정만. |

```python
for transfer in korail.trains.search_transfers("강릉", "목포"):
    first, second = transfer.legs
    print(first.train_no, first.dep_time, "→", transfer.station_name, "→", second.train_no, second.arr_time)

print([station.name for station in korail.trains.transfer_stations("강릉", "목포")])
```

`search_transfers` 는 `search` 와 **같은 요청**이고 여정 종류만 환승입니다. 조건에 맞는 여정이
없으면 `NoResultsError` 를 던집니다. `transfer_stations` 는 역을 코드로 보내므로
`validate_stations` 를 꺼도 역 마스터를 한 번 조회합니다.

> [!NOTE]
> 응답에서 짝이 분명한 두 구간만 여정으로 돌려줍니다. 무엇과 짝인지 알 수 없는 열차는
> 넘겨짚어 잇지 않고 버립니다 — **두 번 갈아타는 여정도 지금은 버립니다.** 버린 것이
> 있으면 `pykorail.models.transfer` 로거에 경고가 남습니다. `TransferStation.english_name`
> 은 서버가 빼고 줄 때가 있어 빈 문자열일 수 있습니다.

#### 운임 조회

예약하기 전에 운임을 봅니다. **로그인하지 않아도 됩니다.**

```python
fares(journey: Train | Transfer) -> list[Fare]
```

```python
train = korail.trains.search("서울", "부산")[0]
for fare in korail.trains.fares(train):
    print(fare.seat_class_name, fare.total)
# 일반실 59800
# 특실 83700
```

`search` · `search_transfers` 가 돌려준 열차나 환승 여정을 넘깁니다. 예약 목록 · 승차권의
열차처럼 조회에 필요한 값(좌석 속성 등)이 없는 열차는 요청 전에 `ValueError` 로 막습니다.

환승 여정은 **구간마다 줄이 나뉘어** 옵니다. 여정 전체의 금액은 객실을 고른 뒤 구간별
`total` 을 더하세요. 상위 객실의 이름은 열차마다 달라서(`"특실"` · `"우등실"`), 이름이 아니라
요금(`charge`)이 붙었는지로 가르는 편이 안전합니다.

```python
transfer = korail.trains.search_transfers("강릉", "목포")[0]
fares = korail.trains.fares(transfer)

print(sum(fare.total for fare in fares if fare.charge == 0))  # 두 구간 모두 일반실로 갈 때
```

> [!IMPORTANT]
> **결제 금액이 아닙니다.** 할인 전의 기준 운임이고, 실제로 낼 금액은 예약한 뒤
> `Reservation.price` 에 있습니다.

#### 호차 · 좌석 조회

좌석을 직접 고르기 위한 조회입니다. **둘 다 로그인이 필요합니다.**

```python
cars(
    train: Train,
    passengers: Sequence[Passenger] | None = None,
    seat_class: SeatClassCode = SeatClass.GENERAL,
) -> list[Car]

seats(
    train: Train,
    car: Car,
    passengers: Sequence[Passenger] | None = None,
    seat_class: SeatClassCode | None = None,
) -> list[CarSeat]
```

| 인자 | 설명 |
| --- | --- |
| `train` | `search` 가 돌려준 열차. |
| `car` | `cars` 가 돌려준 호차. **같은 로그인 세션에서 받은 것**이어야 합니다. |
| `passengers` | 생략 시 어른 1명. 두 호출에 같은 값을 넘기세요. |
| `seat_class` | [`SeatClass`](#seatclass) 코드. `cars` 는 기본 일반실. `seats` 는 생략하면 호차의 객실(`car.seat_class`)을 쓰므로 다시 넘길 필요가 없습니다. 호차에 객실 코드가 없는데 생략하면 `ValueError`. |

```python
from pykorail import SeatClass

train = korail.trains.search("서울", "부산")[0]

cars = korail.trains.cars(train, seat_class=SeatClass.SPECIAL)
car = next(car for car in cars if car.has_seat())

seats = korail.trains.seats(train, car)
print([seat.label for seat in seats if seat.is_available])
# ['15A', '15D', '14B', …]
```

> [!NOTE]
> 순서를 지키세요 — 호차 목록(`cars`) 다음에 좌석 배치(`seats`)입니다. 앱의 화면 순서가
> 그렇고, 호차 목록 없이 좌석 배치를 바로 조회하면 서버가 인증 오류를 돌려준 사례가 있습니다.

#### 운행 달력 조회

오늘부터 약 두 달치의 날짜별 운행 정보를 조회합니다. **로그인하지 않아도 됩니다.**

```python
run_dates() -> list[RunDate]

netfunnel_action_for(run_dates: Sequence[RunDate], departure: date | datetime | str, *, action: NetFunnelActionCode = NetFunnelAction.TRAIN_SEARCH) -> NetFunnelActionCode
```

`RunDate` 는 하루입니다. `run_date`(운행일 `YYYYMMDD`)와 `day`(그 날짜), 성수기 여부
(`is_peak_season`) 말고는 앱의 원문 필드명을 snake_case 로 옮긴 값들(`day_dv_cd` ·
`hldy_dv_cd` · `sale_dd_dv_cd` 와 `o_trn_op_flg` … `x_trn_op_flg`)이라 뜻을 지어 붙이지
않았습니다. 플래그는 `"Y"` · `"N"` 외에 빈 문자열일 수 있어 불리언이 아닙니다.

**일반 열차 조회**의 NetFunnel `aid` 는 출발일이 성수기인지로 갈립니다. 할인상품은
`act_6`(`TRAIN_SEARCH_SPECIAL_OFFER`), 관광열차는 대기열을 거치지 않으므로 이 판정을
쓰지 않습니다 — 자세한 규칙은 [NetFunnel 대기열](#netfunnel-대기열) 참고.
`netfunnel_action_for()` 가 그 판정을 대신합니다 — 성수기면 `act_8_2`, 그 밖이거나
달력에 그날이 없으면 `act_8` 입니다. `datetime` 을 넘기면 KST 로 바꿔 날짜만 봅니다.

코레일톡+ 7.1.0 부터는 **예약** 대기열도 성수기에 갈립니다. `action=NetFunnelAction.RESERVE`
를 주면 `act_14_2`(성수기) 또는 `act_14` 를 돌려줍니다. 다만 기준일이 다릅니다 — 열차
조회는 **조회 조건의 출발일**, 예약은 **첫 여정 열차의 운행일**(`Train.run_date`)입니다.
자정을 넘겨 출발하는 열차는 둘이 달라서, 예약에 출발일을 넘기면 틀린 대기열에 섭니다.
그래서 `departure` 자리에 `Train.run_date` 같은 `"YYYYMMDD"` 문자열도 받습니다(형식이
틀리면 `ValueError`). 성수기 대기열이 없는 동작(결제 등)은 `action` 을 그대로 돌려줍니다.

> [!NOTE]
> 빈 문자열에서는 앱과 다르게 동작합니다. 앱은 운행일·출발일이 모두 비면 달력에서 그날을
> 못 찾은 것으로 보고 평시 대기열(`act_14`)로 가지만, `netfunnel_action_for()` 는
> `ValueError` 를 냅니다. 잘못된 입력이 조용히 평시 줄에 서지 않도록 일부러 엄격하게 했습니다.

```python
from pykorail import NetFunnelAction, netfunnel_action_for

calendar = korail.trains.run_dates()  # 비동기에서는 await korail.trains.run_dates()
aid = netfunnel_action_for(calendar, departure)  # 열차 조회 — 출발일 기준
# 예약 — 운행일 기준. 앱은 운행일이 비었을 때만 출발일을 씁니다.
reserve_aid = netfunnel_action_for(calendar, train.run_date or train.dep_date, action=NetFunnelAction.RESERVE)
```

> [!NOTE]
> 조회 결과를 **캐시하지 않습니다** — 호출마다 요청합니다. 반복해서 쓸 때는 한 번
> 받아 재사용하세요. `NetFunnelHelper` 는 이 결과로 자동으로 엮이지 않습니다.

### `korail.reservations`

| 메서드 | 반환 | 설명 |
| --- | --- | --- |
| `all()` | `list[Reservation]` | 결제 전 예약 전체. 좌석 상세까지 채워 옵니다. |
| `find(rsv_id)` | `Reservation \| None` | 예약번호로 하나. 찾으면 요청 **2회**(목록 + 그 예약의 좌석), 목록에 없으면 1회, `rsv_id` 가 비어 있으면 0회. |
| `create(train, passengers=None, option=GENERAL_FIRST)` | `Reservation` | 예매. 좌석이 없고 예약대기가 열려 있으면 대기를 겁니다. |
| `create_with_seats(train, seats, passengers=None)` | `Reservation` | **고른 좌석으로** 예매. 아래 참고. |
| `create_transfer(transfer, passengers=None, *, seat_class=GENERAL)` | `tuple[Reservation, Reservation]` | **환승 여정의 두 구간을 한 번에** 예매. 아래 참고. |
| `seats(rsv_id)` | `SeatDetail` | 좌석 상세와 발매창구 번호(`seats`·`wct_no` 이름의 튜플). 환승 예약이면 첫 구간의 좌석입니다. |
| `pay(reservation, card)` | `None` | 카드 결제. |
| `cancel(reservation)` | `None` | 예약 취소. 예약번호 단위라, 환승 예약은 어느 구간을 넘겨도 두 구간이 함께 취소됩니다. |

> [!IMPORTANT]
> `all()` 은 예약 하나마다 좌석 상세를 추가 조회합니다. 예약이 N개면 요청이 N+1회
> 나가니, 반복문 안에서 부르지 말고 한 번 받아 재사용하세요.
> **예약 하나만 필요하면 `find()`** 를 쓰세요 — 일치하는 예약이 있으면 목록 1회 + 그 예약의
> 좌석 1회로 끝나고, 없으면 목록 조회 1회에서 멈춥니다.

`create()` 는 예매 직후 예약을 다시 조회해 돌려줍니다 — 반환된 `Reservation` 은
`seats` 와 `wct_no` 가 채워져 있어 바로 `pay()` 에 넘길 수 있습니다.

#### 좌석을 골라 예매하기

`create()` 는 좌석을 서버가 정합니다. 자리를 직접 고르려면 [호차 · 좌석 조회](#호차--좌석-조회)로
받은 좌석을 `create_with_seats()` 에 넘깁니다.

```python
train = korail.trains.search("서울", "부산")[0]

# 좌석은 승객 한 명에 하나씩이라, 두 자리가 남은 호차를 고릅니다.
car = next(car for car in korail.trains.cars(train) if car.remaining_seats >= 2)
picked = [seat for seat in korail.trains.seats(train, car) if seat.is_available][:2]

reservation = korail.reservations.create_with_seats(train, picked, [AdultPassenger(2)])
```

| 인자 | 설명 |
| --- | --- |
| `train` | `search` 가 돌려준 열차. 예약 목록 · 승차권의 열차는 구간 순서가 없어 쓸 수 없습니다. |
| `seats` | `trains.seats()` 가 돌려준 좌석. **승객 한 명에 하나씩**, 전부 같은 객실이어야 합니다. 호차는 달라도 됩니다. 리스트가 아니라 제너레이터를 넘겨도 됩니다. |
| `passengers` | 생략 시 어른 1명. |

객실(일반실 · 특실)은 좌석에 붙어 있어(`CarSeat.seat_class`) 따로 넘기지 않습니다. 좌석 수가
승객 수와 다르거나, 같은 좌석을 두 번 넘기거나, 객실이 섞이면 **요청 전에** `ValueError` 로
막습니다 — 실제 좌석이 걸린 요청이라 서버에 물어보기 전에 거릅니다. 그사이 남이 사 간 좌석은
서버가 거절하고 `KorailError` 가 됩니다.

반환값은 `create()` 와 같습니다 — 바로 `pay()` 나 `cancel()` 에 넘길 수 있습니다.

#### 환승 여정 예매하기

[환승 조회](#환승-조회)로 찾은 여정의 두 구간을 예약번호 하나로 묶어 잡습니다. 구간을 따로
`create()` 하면 첫 구간만 잡히고 둘째가 매진될 수 있습니다 — 이쪽은 한 구간이라도 안 되면
서버가 통째로 거절합니다. 좌석은 서버가 정합니다.

```python
transfer = korail.trains.search_transfers("강릉", "목포")[0]
first, second = korail.reservations.create_transfer(transfer)

print(first.pnr_no == second.pnr_no)  # True — 예약번호는 하나입니다
print(first.train.arr_name, first.seats, second.seats)
```

| 인자 | 설명 |
| --- | --- |
| `transfer` | `search_transfers` 가 돌려준 여정. 두 구간이어야 합니다. |
| `passengers` | 생략 시 어른 1명. |
| `seat_class` | 두 구간에 함께 적용할 객실 — [`SeatClass`](#seatclass) 코드. 기본 일반실. |

반환값은 **구간마다 하나씩, 예약 둘**이고 타는 순서입니다. 둘은 예약번호가 같고 각자 그
구간의 열차와 좌석을 가집니다. 열차 한 편을 넘기면 `TypeError`, 구간이 둘이 아니거나 열차에
구간 순서가 없으면 요청 전에 `ValueError` 입니다.

환승 예약은 예약번호 하나에 구간이 둘이라, 보통 예약과 다른 점이 셋 있습니다.

- **취소는 예약 전체입니다.** `cancel()` 에 둘 중 어느 것을 넘겨도 두 구간이 함께 취소됩니다.
- **`price` 는 예약 전체의 금액입니다.** 서버가 두 항목에 같은 값을 싣습니다 — 둘을 더하면
  두 배가 됩니다. 구간별 금액은 `seats` 의 좌석 금액에 있습니다.
- **`all()` 에는 구간마다 한 줄씩** 나오고, `find()` 는 첫 구간의 예약을 돌려줍니다.

```python
first, second = korail.reservations.create_transfer(transfer)

print(first.price)  # 75100 — 두 구간의 합
print([seat.price for seat in first.seats])  # [27600] — 첫 구간만
korail.reservations.cancel(first)  # 두 구간이 함께 취소됩니다
```

### `korail.tickets`

| 메서드 | 반환 | 설명 |
| --- | --- | --- |
| `all()` | `list[Ticket]` | 발권 완료된 승차권. 실제 좌석번호까지 확정해서 옵니다. |
| `refund_fee(ticket)` | `RefundFee` | 환불 수수료 **조회만**. 환불하지 않습니다. |
| `refund(ticket)` | `None` | 환불. |

목록 응답에는 실제 좌석번호가 없어 승차권마다 상세를 한 번 더 조회합니다.

```python
fee = korail.tickets.refund_fee(ticket)
print(fee)  # 53,400원 환불 (수수료 5,600원)

if fee.refundable and fee.fee < 10000:
    korail.tickets.refund(ticket)
```

수수료는 출발까지 남은 시간에 따라 달라집니다. 조회 시점과 실제 환불 시점 사이에
구간이 바뀌면 금액도 바뀝니다 — `refund_fee()` 는 **그 시점의 견적**입니다.

### `RefundFee`

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `fee` | `int` | 환불 수수료(원) |
| `amount` | `int` | 실제로 돌려받는 금액(원) |
| `usable_mileage` | `int` | 이 환불에 쓸 수 있는 마일리지 |
| `refundable` | `bool` | 환불 가능 여부. `False` 면 `amount` 는 의미 없음 |
| `period_code` | `str` | 수수료를 계산한 반환 시기 구분 코드 |

### `korail.membership`

마일리지와 할인쿠폰을 조회합니다. 전부 **로그인이 필요합니다.**

| 메서드 | 반환 | 설명 |
| --- | --- | --- |
| `mileage(since=None, until=None, *, kind=KTX, inquiry=ALL, page=1)` | `Mileage` | 마일리지 잔액과 적립 · 사용 내역 한 쪽. |
| `coupons(page=1)` | `list[Coupon]` | 가진 할인쿠폰. 없으면 빈 리스트. 쪽 수는 응답에서 확인되지 않아 싣지 않았습니다 — 다음 쪽이 비면 끝입니다. |

```python
mileage = korail.membership.mileage()
print(mileage.total, mileage.rail_point, mileage.expiring)  # 13000 500 120

for entry in mileage.entries:
    print(entry.date, entry.kind_name, entry.movement, entry.amount)
# 20261003 KTX 마일리지 적립 2990
# 20260921 KTX 마일리지 사용 -1000
```

| 인자 | 설명 |
| --- | --- |
| `since` · `until` | 내역을 볼 기간 (`datetime.date`). `until` 을 생략하면 오늘(KST), `since` 를 생략하면 `until` 의 30일 전. `since` 가 더 늦으면 `ValueError`. `datetime` 을 넘겨도 되고, 그때는 `trains.search` 처럼 KST 로 읽어 날짜만 씁니다. |
| `kind` | 어느 장부의 내역인지 — [`MileageType`](#mileagetype) 코드. 기본 KTX 마일리지. |
| `inquiry` | 적립 · 사용 구분 — [`MileageInquiry`](#mileageinquiry) 코드. 기본 전체. |
| `page` | 쪽 번호. 1 부터이고, 1 보다 작으면 `ValueError`. 한 쪽에 20건씩 요청합니다. |

**잔액은 조건과 무관하게 함께 옵니다.** `kind` · `inquiry` · 기간은 내역(`entries`)만
거릅니다. 내역이 한 쪽을 넘으면 `page_count` 만큼 쪽 번호를 올려 다시 조회하세요.

```python
from datetime import date
from pykorail import MileageInquiry

since = date(2026, 7, 1)
used = korail.membership.mileage(since, inquiry=MileageInquiry.USE)
entries = list(used.entries)

for page in range(2, used.page_count + 1):
    entries += korail.membership.mileage(since, inquiry=MileageInquiry.USE, page=page).entries
```

### `korail.airport_bus`

KTX 공항버스의 정류장 · 시간표 · 좌석을 조회합니다. **전부 로그인 없이 됩니다.**

> [!IMPORTANT]
> **코레일이 파는 것은 광명역에서 떠나는 편뿐입니다** — 광명역 → 인천공항T1 · 인천공항T2.
> 인천공항 → 광명역이나 송도국제교가 낀 구간은 빈 리스트가 돌아옵니다. 버스가 안 다니는 것이
> 아니라 코레일이 그 구간의 표를 팔지 않는 것입니다. 앱도 출발 정류장을 광명역 하나로
> 고정하고 도착(T1 · T2)만 고르게 합니다.

| 메서드 | 반환 | 설명 |
| --- | --- | --- |
| `stops(refresh=False)` | `list[BusStop]` | 정류장 목록. 클라이언트 수명 동안 캐시합니다. |
| `search(dep, arr, depart_after=None)` | `list[AirportBus]` | 시간표. 없으면 빈 리스트. |
| `seats(bus, passengers=None)` | `list[CarSeat]` | 한 편의 좌석 배치. |

```python
print([stop.name for stop in korail.airport_bus.stops()])
# ['광명역', '인천공항T1', '인천공항T2', '송도국제교']

buses = korail.airport_bus.search("광명역", "인천공항T1", datetime(2026, 10, 16, 6, 0))
bus = next(bus for bus in buses if bus.has_seat())
print(bus)  # [공항버스 08008] 10/16 06:00~06:50  광명역~인천공항T1  24석

seats = korail.airport_bus.seats(bus)
print([seat.seat_no for seat in seats if seat.is_available])
```

| 인자 | 설명 |
| --- | --- |
| `dep` · `arr` | 정류장 **이름** (`stops()` 의 `name`). 목록에 없으면 요청 전에 `StationNotFoundError`. 목록에 있어도 코레일이 팔지 않는 구간이면 빈 리스트입니다. |
| `depart_after` | 그날, 이 시각 **이후** 출발. tz 없으면 KST 로 해석, 있으면 KST 로 변환. 생략 시 현재. |
| `bus` | `search` 가 돌려준 편. |
| `passengers` | 생략 시 어른 1명. |

좌석은 열차의 좌석 조회와 같은 모델([`CarSeat`](#carseat))로 옵니다. 공항버스는 좌석 식별자와
표시가 둘 다 번호(`"1"`)이고, 호차는 늘 `"0001"`, 객실은 일반실입니다.

> [!NOTE]
> 조회만 됩니다. 공항버스 **예매**는 아직 없습니다.

## 모델

전부 불변(`frozen=True`)이고 `from_response()` 로 생성됩니다. `dataclasses.replace()`
로 파생 객체를 만들 수 있습니다.

### `Train` (← `Schedule`)

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `train_no` | `str` | 열차 번호 (`"101"`) |
| `train_type` · `train_type_name` | `str` | 종별 코드 · 이름 (`"00"` / `"KTX"`) |
| `train_group` | `str` | 열차 그룹 코드 |
| `dep_name` · `dep_code` · `dep_date` · `dep_time` | `str` | 출발역 · 코드 · `YYYYMMDD` · `HHMMSS` |
| `arr_name` · `arr_code` · `arr_date` · `arr_time` | `str` | 도착 쪽 동일 |
| `run_date` | `str` | 운행일 `YYYYMMDD` |
| `delay_time` | `str` | 예상 지연 |
| `special_seat` · `general_seat` | `str` | 좌석 코드 (`"11"` = 가능) |
| `wait_reserve_flag` | `int` | `9` = 예약대기 가능, `-1` = 미적용 |
| `dep_run_order` · `arr_run_order` | `str` | 출발 · 도착역의 운행 순서. 호차 · 좌석 조회가 구간을 이 값으로 가리킵니다 |
| `dep_cons_order` · `arr_cons_order` | `str` | 출발 · 도착역의 구성 순서. 좌석을 지정한 예매가 운행 순서와 함께 돌려보냅니다 |
| `seat_attribute` | `str` | 이 열차 행의 좌석 속성 코드. 운임 · 호차 · 좌석 조회와 좌석 지정 · 환승 예매가 이 값을 보냅니다 — 예매는 비면 일반석 `015` 로 대체합니다 |

| 메서드 · 속성 | 반환 | 설명 |
| --- | --- | --- |
| `has_seat()` | `bool` | 특실 또는 일반실 좌석 있음 |
| `has_special_seat()` · `has_general_seat()` | `bool` | 각각 |
| `has_waiting_list()` | `bool` | 예약대기 가능 |
| `departure` · `arrival` | `datetime \| None` | 출발 · 도착 일시(KST). 날짜나 시각이 비었거나 형식이 틀리면 `None` |
| `duration_minutes` | `int \| None` | 소요 시간(분). 날짜가 있으면 일시끼리 빼므로 이틀에 걸친 운행도 맞습니다. 날짜가 없으면 시각만으로 잽니다. |
| `duration_text` | `str \| None` | 사람이 읽는 소요 시간 (`"3시간 30분"`). 1시간 미만이면 `"45분"`. |
| `summary()` | `str` | 좌석 정보를 뺀 한 줄 요약 |

### `Reservation`

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `train` | `Train` | **참조** — `reservation.train.dep_name` |
| `pnr_no` | `str` | 예약번호 (PNR) |
| `price` | `int` | 결제 예정 금액 |
| `seat_count` | `int` | 좌석 수 |
| `seats` | `tuple[Seat, ...]` | 배정 좌석 |
| `wct_no` | `str \| None` | 발매창구 번호 — 결제에 필요 |
| `buy_limit_date` · `buy_limit_time` | `str` | 구입기한 |
| `is_waiting` | `bool` (속성) | 예약대기 여부 |
| `buy_limit` | `datetime \| None` (속성) | 구입기한 일시(KST). 예약대기면 `None` |

> **`train` 의 날짜.** 예약 목록은 운행일 하나만 줍니다. 여정 상세가 출발·도착 날짜를 주면 그 값을 쓰고,
> 주지 않으면 운행일을 출발일로 두고 도착 시각이 출발보다 이르면 다음 날을 도착일로 봅니다. 상세 응답의
> 날짜 필드는 APK 모델에서 확인했고, 실서버 응답에 채워져 오는지는 확인하지 못했습니다
> (`docs/protocol-evidence-7.0.8.json`의 `reservation_journey_dates`).

### `SeatDetail`

`korail.reservations.seats()` 가 돌려주는 이름 있는 튜플입니다. 풀어 쓰는 기존 코드(`seats, wct_no = …`)는 그대로 동작합니다.

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `seats` | `list[Seat]` | 첫 여정의 좌석. 조회 결과가 없으면 빈 목록 |
| `wct_no` | `str \| None` | 발매창구 번호. 결제에 필요합니다 |

### `Ticket`

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `train` | `Train` | **참조** |
| `seat_no` · `car_no` | `str` | 좌석 · 호차 |
| `price` | `int` | 결제 금액 |
| `pnr_no` | `str` | 예약번호 |
| `sold_on` | `date \| None` (속성) | 발매일. `sale_date` 를 날짜로 바꾼 값 |
| `original_wct_no` · `original_refund_sale_date` · `original_sale_seq_no` · `original_refund_pwd` | `str` | 환불에 필요한 원권 식별자 4종 (앱의 `hOrgtkWctNo` · `hOrgtkRetSaleDt` · `hOrgtkSaleSqno` · `hOrgtkRetPwd`) |
| `ticket_no` | `str` (속성) | 위 4개를 하이픈으로 이은 승차권 번호 |

### `Seat`

| 필드 | 설명 |
| --- | --- |
| `car_no` · `seat_no` | 호차 · 좌석번호 |
| `seat_class_name` | 일반실 / 특실 |
| `passenger_type_name` | 어른 / 어린이 … |
| `price` · `original_price` · `discount` | 결제액 · 정가 · 할인액 |
| `is_waiting` (속성) | 좌석번호가 비어 있으면 예약대기 자리 |

### `Transfer`

`korail.trains.search_transfers()` 가 돌려주는 환승 여정 하나입니다. 열차를 상속하지 않고
**참조**합니다.

| 필드 · 속성 | 타입 | 설명 |
| --- | --- | --- |
| `legs` | `tuple[Train, ...]` | 타는 순서대로 구간들. 지금은 항상 둘입니다 |
| `first` · `second` | `Train` (속성) | 처음 타는 열차 · 갈아탄 뒤의 열차 |
| `station_name` | `str \| None` (속성) | 갈아타는 역 이름. 첫 열차의 도착역과 둘째 열차의 출발역이 다르면 `None` |
| `has_seat()` | `bool` (메서드) | 두 구간 **모두** 좌석이 있는지 |

`TransferStation` 은 `korail.trains.transfer_stations()` 가 돌려주는 환승 가능 역입니다 —
`code` (`"0015"`) · `name` (`"대전"`) · `english_name` (`"Daejeon"`).

### `Fare`

`korail.trains.fares()` 가 돌려주는 한 구간 · 한 객실의 운임입니다.

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `train_no` | `str` | 열차 번호 |
| `journey_no` | `str` | 여정 안의 구간 번호 (`"0001"` 부터). 환승 여정은 구간마다 줄이 나뉩니다 |
| `seat_class_name` | `str` | 객실 이름 (`"일반실"` · `"특실"` · `"우등실"`). 열차에 따라 다릅니다 |
| `price` | `int` | 운임(원). 객실과 무관하게 같습니다 |
| `charge` | `int` | 요금(원). 특실 · 우등실에 붙고 일반실은 `0` |
| `total` | `int` | 합계(원) — 운임 + 요금 |

### `Car`

`korail.trains.cars()` 가 돌려주는 호차 하나입니다.

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `car_no` | `str` | 호차 번호. 서버가 준 문자열 그대로입니다 (`"0003"`) |
| `seat_class` · `seat_class_name` | `str` | 객실 구분 코드 · 이름 (`"1"` / `"일반실"`) |
| `seat_count` | `int` | 전체 좌석 수 |
| `remaining_seats` | `int` | 남은 좌석 수 |
| `attributes` | `tuple[SeatAttribute, ...]` | 이 호차에서 고를 수 있는 좌석 속성 |
| `has_seat()` | `bool` (메서드) | 남은 좌석이 있는지 |

`SeatAttribute` 는 좌석 속성 하나입니다 — `code` (`"015"`) 와 `name` (`"일반석"`).

### `CarSeat`

`korail.trains.seats()` 가 돌려주는 좌석 하나입니다. 예약이 끝난 뒤의 배정 좌석인
[`Seat`](#seat) 과는 다릅니다 — 아직 팔리지 않았을 수도 있는 좌석 배치입니다.

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `car_no` | `str` | 호차 번호 (`"0003"`) |
| `seat_class` | `str` | 이 좌석을 조회한 객실 구분 코드 (`"1"` · `"2"`). 좌석 지정 예매가 이 값을 씁니다 |
| `seat_no` | `str` | 좌석 **식별자** (`"57"`). 좌석을 가리킬 때는 이 값을 씁니다 |
| `label` | `str` | 화면에 보이는 좌석 표시 (`"15A"`) |
| `sale_flag` | `str` | 판매 가능 표시 (`"Y"` = 가능) |
| `is_available` | `bool` (속성) | 지금 살 수 있는 좌석인지 |
| `direction` · `attribute` · `extra_attribute` | `str` | 방향 · 요청 좌석 · 기타 속성 코드 |
| `message` | `str` | 좌석에 붙은 안내 문구 |

### `AirportBus`

`korail.airport_bus.search()` 가 돌려주는 공항버스 한 편입니다.

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `bus_no` | `str` | 편 번호. 서버가 준 문자열 그대로입니다 (`"08008"`) |
| `dep_name` · `dep_code` · `arr_name` · `arr_code` | `str` | 출발 · 도착 정류장의 이름과 코드 |
| `run_date` · `dep_date` · `arr_date` | `str` | 운행일 · 출발일 · 도착일 `YYYYMMDD` |
| `dep_time` · `arr_time` | `str` | 출발 · 도착 시각 `HHMMSS` |
| `remaining_seats` | `int` | 남은 좌석 수 |
| `price` | `int` | 운임(원). 어른 한 명 기준입니다 |
| `group` · `bus_type` | `str` | 운행 그룹 코드 · 종별 코드 (`"980"` / `"98"`) |
| `dep_run_order` · `arr_run_order` | `str` | 정류장의 운행 순서. 좌석 조회가 구간을 이 값으로 가리킵니다 |
| `departure` · `arrival` | `datetime \| None` (속성) | 출발 · 도착 일시(KST). 날짜나 시각이 비었거나 형식이 틀리면 `None` |
| `has_seat()` | `bool` (메서드) | 남은 좌석이 있는지 |

### `BusStop`

`korail.airport_bus.stops()` 가 돌려주는 정류장입니다 — `code` (`"0501"`) 와 `name` (`"광명역"`).

### `Mileage`

`korail.membership.mileage()` 가 돌려주는 잔액과 내역 한 쪽입니다.

| 필드 · 속성 | 타입 | 설명 |
| --- | --- | --- |
| `ktx` | `int` | KTX 마일리지 |
| `samsung_card` | `int` | KTX 삼성카드로 쌓은 마일리지 |
| `total` | `int` (속성) | 위 둘의 합 — 앱이 "KTX 마일리지" 로 보여 주는 숫자 |
| `rail_point` | `int` | 레일포인트. `total` 에는 들어가지 않습니다 |
| `expiring` | `int` | 이번 달 소멸 예정 |
| `info` | `str` | 마일리지 안내 문구 |
| `page_count` | `int` | 조건에 맞는 내역의 전체 쪽 수 |
| `entries` | `tuple[MileageEntry, ...]` | 이번 쪽의 내역 |

### `MileageEntry`

적립 · 사용 내역 한 줄입니다.

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `date` | `str` | 날짜 `YYYYMMDD` |
| `kind_name` | `str` | 어느 마일리지인지 (`"KTX 마일리지"`) |
| `movement` | `str` | 적립인지 사용인지 (`"적립"` · `"사용"`) |
| `detail` | `str` | 서버가 붙인 설명 (`"마일리지 적립 (열차이용)"` · `"코레일"`) |
| `amount` | `int` | 증감. 적립은 양수, 사용은 음수 |
| `day` | `date \| None` (속성) | `date` 를 날짜로 바꾼 값 |

### `Coupon`

`korail.membership.coupons()` 가 돌려주는 할인쿠폰 한 장입니다.

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `coupon_no` | `str` | 쿠폰번호 |
| `title` | `str` | 쿠폰 이름 |
| `description` | `str` | 덧붙는 설명 |
| `tag` | `str` | 앱이 꼬리표로 보여 주는 짧은 구분 |
| `valid_from` · `valid_until` | `str` | 쓸 수 있는 기간 `YYYYMMDD`. **승차일** 기준입니다 |
| `starts_on` · `ends_on` | `date \| None` (속성) | 위 기간을 날짜로 바꾼 값 |
| `guide` | `str` | 이용 안내 |

쿠폰번호는 번호만 알면 다른 계정에 등록할 수 있는 값이라 `repr` 은 뒤 4자리만
남깁니다. 할인율 · 할인액은 값의 형식을 확인하지 못해 싣지 않았습니다 — 무슨 쿠폰인지는
`title` 로 읽으세요.

### `Station`

| 필드 | 설명 |
| --- | --- |
| `code` · `name` | 역 코드 (`"0020"`) · 이름 (`"부산"`) |
| `latitude` · `longitude` | 좌표 (`float \| None`) |
| `group` | 노선 그룹 코드 — 같은 값이면 같은 노선군 |
| `major` · `is_major` · `major_rank` (속성) | 주요역 노출 순번 · 주요역 여부 · 순번을 정수로 (`int \| None`) |
| `popup_type` · `popup_message` | 역 선택 시 안내 (`"0"` = 안내 없음) |

### `Card`

```python
Card(number, password, verify_number, expire, installment=0, is_corporate=False)
```

| 필드 | 설명 |
| --- | --- |
| `number` | 카드번호 (하이픈 없이) |
| `password` | 카드 비밀번호 **앞 2자리** |
| `verify_number` | 개인카드=생년월일 `YYMMDD`, 법인카드=사업자등록번호 |
| `expire` | 유효기간 `YYMM` |
| `installment` | 할부 개월. `0` = 일시불 |
| `is_corporate` | 법인카드 여부 |

앞자리 `0` 이 의미를 가지므로 **전부 문자열**입니다. 빈 값·정수·음수 할부는 생성
시점에 `ValueError` 로 막습니다. `repr` 은 카드번호 뒤 4자리만 남깁니다.

```python
repr(card)  # Card(number='****5678', installment=0, is_corporate=False)
```

---

## 승객

| 클래스 | 유형 코드 | 할인 코드 | 대상 |
| --- | --- | --- | --- |
| `AdultPassenger` | `1` | `000` | 어른 |
| `ChildPassenger` | `3` | `000` | 어린이 |
| `ToddlerPassenger` | `3` | `321` | 유아 |
| `SeniorPassenger` | `1` | `131` | 경로 |
| `Disability1To3Passenger` | `1` | `111` | 중증 장애인 (1~3급) |
| `Disability4To6Passenger` | `1` | `112` | 경증 장애인 (4~6급) |
| `GuideDogPassenger` | `1` | `173` (미확인) | 안내견 동반 승객 (시각장애인) |

> [!WARNING]
> **자격이 필요한 할인은 계정에 자격이 없으면 서버가 거절하지 않고 어른 운임(할인
> 없음)으로 예약합니다.** 2026-10-16 중증 장애인(`111`)에서 확인했고, 다른 할인 코드와
> 자격이 있는 계정은 확인하지 않았습니다. 예약 뒤에는 `reservation.seats` 의
> `passenger_type_name` 이 기대한 유형인지 확인하세요.

```python
Passenger(count=1, discount_type=None, card="", card_no="", card_pw="")
```

유형 · 할인 · 등록카드가 같은 승객은 **자동으로 한 블록으로 합쳐져** 전송됩니다.
순서가 섞여 있어도 정확히 합쳐집니다.

```python
from pykorail import AdultPassenger, ChildPassenger, Passenger

Passenger.reduce([AdultPassenger(1), ChildPassenger(1), AdultPassenger(2)])
# [AdultPassenger(count=3, ...), ChildPassenger(count=1, ...)]
```

### 안내견 (`GuideDogPassenger`)

> [!WARNING]
> **할인 코드 `173` 은 실서버로 확인되지 않았습니다.** 코레일톡+ 7.0.8 APK 에서는
> 보호(AppSuit/AlienGuard) 문자열이라 값이 읽히지 않아, 외부 비공식 클라이언트의
> 기록을 그대로 옮겼습니다. 2026-10-16 실서버에서 중증 1 + 안내견 1 조합의
> **예약은 서버가 `ERR299943`("예약할인이 지원되지 않습니다")로 거절했습니다.** 다만
> 이 계정의 중증 단독 예약도 위 경고대로 어른 운임으로 강등됐으므로, **이 거절이
> `173` 때문인지 이 계정에 자격이 없어서인지 가리지 못했습니다.** 그래서 **지금
> `GuideDogPassenger` 로 예매하면 실패할 수 있습니다.** 근거와 한계는
> `docs/protocol-evidence-7.0.8.json` 의 `guide_dog_passenger` · `live_validation`
> 과 #60.

안내견은 유형 코드가 어른과 같은 `1` 이지만 **어른의 하위 클래스가 아닙니다.**
예매 폼에서는 할인 코드가 달라 별도 블록으로 나가야 하고, 열차 조회 폼에서는
**어른 칸(`txtPsgFlg_1`)에 더해져** 전송됩니다 (코레일톡+ 7.0.8
`TrainScheduleViewModel` 의 인원 칸 합산). 유아를 어린이 칸에 더하는 것과 같은
방식이라, `korail.trains.search(..., passengers=[Disability1To3Passenger(1), GuideDogPassenger(1)])`
의 조회 폼은 `txtPsgFlg_1=1`, `txtPsgFlg_4=1` 이 됩니다.

좌석 조회의 총 인원(`totPsgCnt`)과 좌석 지정 예매의 "좌석 수 = 승객 수" 검사에서도
안내견을 **한 명으로 셉니다** — 앱이 `Passengers.sum()` 을 그대로 `txtTotPsgCnt` 에
싣기 때문입니다.

**앱의 인원 제약은 걸지 않습니다.** 앱의 인원 선택기는 안내견 수가 중증 · 경증 장애인
합계를 넘으면 막지만(`PassengersBottomSheetKt.warningPassengerType`), pykorail 은
그 조합을 막지 않고 그대로 보냅니다. 제약 위반은 서버가 판단합니다. 그래서 다음
조합도 요청 자체는 나갑니다 — 서버가 거절할 수 있습니다.

```python
from pykorail import GuideDogPassenger

korail.trains.search("서울", "부산", passengers=[GuideDogPassenger(1)])
```

**공항버스는 지원하지 않습니다.** 앱의 공항버스 승객 목록
(`PassengerType.airportList()`)에는 어른 · 어린이만 있고 안내견 · 장애인이 없습니다.
안내견은 열차 조회 · 예매에만 쓰세요.

## 옵션

### `TrainType`

폼 필드에 그대로 실려 나가는 값이라 `Enum` 이 아닌 문자열 상수입니다
(`str` 혼합 `Enum` 은 파이썬 버전에 따라 `str()` 결과가 달라져 전송 값이 깨집니다).
정적 검사는 `TrainTypeCode` · `ReserveOptionCode` 리터럴 별칭이 담당해서,
`train_type="999"` 같은 오타는 `ty` 가 잡습니다.

| 상수 | 코드 |
| --- | --- |
| `KTX` · `KTX_SANCHEON` | `100` |
| `SAEMAEUL` · `ITX_SAEMAEUL` | `101` |
| `MUGUNGHWA` · `NURIRO` | `102` |
| `TONGGUEN` | `103` |
| `ITX_CHEONGCHUN` | `104` |
| `AIRPORT` | `105` |
| `ALL` (기본) | `109` |

같은 코드를 공유하는 이름들은 **별칭이지 오타가 아닙니다.**

### `ReserveOption`

좌석 유무에 따라 동작이 다릅니다.

| 옵션 | 좌석이 있을 때 | 좌석이 없어 예약대기를 걸 때 |
| --- | --- | --- |
| `GENERAL_FIRST` (기본) | 일반실 우선, 없으면 특실 | 일반실 |
| `SPECIAL_FIRST` | 특실 우선, 없으면 일반실 | 특실 |
| `GENERAL_ONLY` | 일반실만 | 일반실 |
| `SPECIAL_ONLY` | 특실만 | 특실 |

### `SeatClass`

호차 · 좌석 조회의 객실 구분입니다. 타입 별칭은 `SeatClassCode` 입니다.

| 이름 | 코드 |
| --- | --- |
| `GENERAL` (기본) | `1` |
| `SPECIAL` | `2` |

### `MileageType`

마일리지 내역을 볼 장부입니다. 타입 별칭은 `MileageTypeCode` 입니다.

| 이름 | 코드 |
| --- | --- |
| `KTX` (기본) | `1` |
| `RAIL_POINT` | `2` |

### `MileageInquiry`

마일리지 내역의 적립 · 사용 구분입니다. 타입 별칭은 `MileageInquiryCode` 입니다.

| 이름 | 코드 | 앱의 "조회 유형" |
| --- | --- | --- |
| `ALL` (기본) | `0` | 전체 |
| `SAVE` | `1` | 적립 |
| `USE` | `2` | 사용 |


## 이름 변경 (0.6.0)

옛 이름은 0.6.0 에서도 같은 값을 돌려줍니다. 읽으면 `DeprecationWarning` 이 나가고, 0.7.0 에서 지웁니다.

| 옛 이름 | 새 이름 |
| --- | --- |
| `Reservation.rsv_id` | `pnr_no` |
| `Reservation.seat_no_count` · `Ticket.seat_no_count` | `seat_count` |
| `Seat.car` · `Seat.seat` | `car_no` · `seat_no` |
| `Seat.seat_type` · `Seat.passenger_type` | `seat_class_name` · `passenger_type_name` |
| `Ticket.sale_info1`–`sale_info4` | `original_wct_no` · `original_refund_sale_date` · `original_sale_seq_no` · `original_refund_pwd` |
| `Korail.logined` (`AsyncKorail` 도 같음) | `is_logged_in` |

생성자를 키워드로 직접 부르던 코드(`Reservation(rsv_id=...)` 등)는 깨집니다. `dataclasses.replace(r, rsv_id=...)` 도 경고 없이 `TypeError` 가 납니다. `from_response` 로
만든 객체와 조회 결과는 그대로입니다.

## 예외

```
PykorailError
├── KorailError            코레일이 strResult=FAIL 로 응답
│   ├── NeedToLoginError   P058
│   ├── NoResultsError     P100 · WRG000000 · WRD000061 · WRT300005
│   ├── SoldOutError       IRT010110 · ERR211161
│   └── LoginFailedError   로그인 실패 전부 — 자격증명 누락 · 키 발급 실패 · 서버 거부
│       └── PasswordChangeRequiredError  WRC000420 — 비밀번호 변경 안내에 걸림
├── NetFunnelError         대기열 게이트 실패
├── StationNotFoundError   요청 전 클라이언트 검증 — 역 이름이 없음
├── PastDepartureError     요청 전 클라이언트 검증 — 이미 지난 시각
└── TransportError         세션 생성 실패 / 비 JSON 응답
    └── HttpStatusError    코레일 형식이 아닌 HTTP 4xx·5xx
        └── AccessRestrictedError  이용제한 봉투 code=-2000 (상태 무관)
```

`except PykorailError` 하나로 라이브러리 유래 실패를 전부 잡을 수 있습니다.
매칭되지 않은 코드는 `KorailError` 로 올라옵니다. 어느 쪽이든 서버가 준 메시지
(`h_msg_txt`)와 코드(`h_msg_cd`)가 `msg` · `code` 에 실립니다 — 서버가 메시지를 주지
않았을 때만 타입의 기본 문구(`"No Results"` 등)가 들어갑니다. **분기는 메시지가 아니라
타입이나 `code` 로 하세요.** 문구는 서버가 바꿀 수 있습니다.

```python
from pykorail import KorailError, SoldOutError

try:
    reservation = korail.reservations.create(train)
except SoldOutError:
    ...  # 매진 — 다음 열차로
except KorailError as exc:
    print(exc.msg, exc.code)  # 서버 메시지와 h_msg_cd
```

`HttpStatusError` 는 서버가 요청 자체를 거절했다는 뜻입니다 — 비밀번호 오류나
"열차 없음" 이 아닙니다. 상태 코드(`status_code`)와 서버가 준 `code` · `message`
(`msg`)를 그대로 담습니다.

실행 환경 검증에 걸리면 `code=-2000` 이용제한 안내가 오고, 하위 타입
`AccessRestrictedError` 가 됩니다. 관측된 것은 HTTP 403 이지만, 같은 봉투가 다른
상태(200 등)로 와도 이 타입입니다 — `status_code` 에는 실제 상태가 담깁니다. 이때는
같은 요청을 곧바로 반복하지 마세요. 대기 루프라면 이 타입만 따로 잡아 멈추면 됩니다.

```python
from pykorail import AccessRestrictedError, HttpStatusError

try:
    korail.login(korail_id, korail_pw)
except AccessRestrictedError as exc:
    print(exc)  # 이용제한: 원활한 서비스를 위해 ... (HTTP 403, -2000)
except HttpStatusError as exc:
    print(exc.status_code, exc.code, exc.msg)  # 그 밖의 거절 (502 등)
```

`PasswordChangeRequiredError` 는 같은 비밀번호를 6개월 넘게 쓴 계정에서 납니다. 서버는
이때 로그인 응답을 **성공으로** 보내지만 세션을 인증하지 않아서, 로그인된 것으로 치면 이후의
**로그인이 필요한 호출**이 이유 없이 `NeedToLoginError` 가 됩니다 — 같은 세션에서 열차 조회는
그대로 됐습니다. 그래서 로그인 단계에서 막습니다.
자격증명이 틀린 것이 아니니 **다시 시도해도 같습니다** — 코레일톡 앱이나 홈페이지에서 안내를
처리한 뒤 로그인하세요. `LoginFailedError` 의 하위 타입이라 기존 `except LoginFailedError` 도
그대로 잡고, 서버의 안내문이 `msg` 에 실립니다.

```python
from pykorail import LoginFailedError, PasswordChangeRequiredError

try:
    korail.login(korail_id, korail_pw)
except PasswordChangeRequiredError as exc:
    print(exc.msg)  # 6개월 이상 동일한 비밀번호를 사용하고 있습니다. …
    raise SystemExit("앱에서 비밀번호 변경 안내를 처리해 주세요") from exc
except LoginFailedError:
    ...  # 아이디 · 비밀번호가 틀림 등
```

`PastDepartureError` 는 요청 시각(`requested`)과 판정 기준 시각(`now`)을 함께
담습니다 — 오래 도는 대기 루프에서 "언제 지나갔는지" 를 로그로 남길 수 있습니다.

`StationNotFoundError` 는 오타 후보까지 알려줍니다.

```python
korail.trains.search("서울역", "부산")
# StationNotFoundError: 존재하지 않는 역입니다: '서울역' (혹시 '서울'?)
```

새 응답 코드는 `KorailError` 를 상속하고 `codes` · `default_msg` 만 채우면
자동으로 매핑됩니다 — 등록 테이블이 없습니다.

## 기기 프로파일

User-Agent는 프로파일 유무와 무관하게 `korailtalk`입니다. 프로파일은 NetFunnel 대기열의
Dalvik User-Agent(모델·OS·빌드ID)와, DynaPath 선언 토큰에 실리는 기기 사실(model·release·
sdk)을 함께 정합니다. `android_id` 는 토큰의 `iid` 로 실리고 저장·복원에도 쓰입니다 —
두 ID를 함께 저장해 재시작 후에도 같은 기기로 보이게 하세요.

> [!IMPORTANT]
> **기본 DynaPath 토큰은 Flow-1 선언 토큰입니다(하드웨어 서명 아님).** 기본 엔진
> `DeclarationDynaPathEngine` 은 네이티브 `libdp_ffi_android.so` 의 선언 토큰 코덱을 순수
> 파이썬으로 바이트 단위 재현한 것으로(`.so` 불필요), 평문 봉투를 SHA256-CTR 로 XOR 하고
> 워드별 커스텀 base62 로 인코딩한 `201…` 문자열입니다. 실제 앱과 op(`es`)·필드 구성이 다를 수
> 있고 하드웨어 서명(Flow-2, StrongBox/TEE)은 재현하지 못합니다. 그래도 동작하는 것은 서버가
> 본문을 검사하지 않기 때문입니다 — `seatMovie.ScheduleView` 에서 `201` 프리픽스만 보는 것이
> 관측됐고, 2026-10-28 승인된 실서버 흐름(로그인→조회→예약→즉시 취소→로그아웃)도 통과했습니다.
> 서버가 본문이나 하드웨어 서명 토큰(enroll 챌린지에 `beginRequest`→`finishRequest` 로 응답)을
> 검사하게 되면 무효가 될 수 있습니다. 실기기 `board`·attestation 값이 필요하면
> `Korail(dynapath_engine=...)` 로 커스텀 엔진을 주입하세요. 자세한 근거는
> `docs/protocol-evidence-7.0.10.json` 에 있습니다.
>
> 이전 버전의 `pykorail.auth.DynaPathMasterEngine`(`201` + 임의 영숫자)은 제거됐습니다. 직접
> 쓰던 코드는 `pykorail.auth.DeclarationDynaPathEngine` 으로 바꾸세요 — 토큰은
> `generate_token(op_id=..., device_id=...)` 로 만들고, 클라이언트에 넣으려면
> `Korail(dynapath_engine=DeclarationDynaPathEngine(...))` 를 씁니다.

```python
from pykorail import Korail
from pykorail.device import profile_by_id, random_profile

# 두 ID를 함께 저장해야 재시작 후에도 같은 기기 ID를 씁니다.
profile = profile_by_id(saved_id, android_id=saved_android_id) or random_profile()
save(profile.id, profile.android_id)

korail = Korail(device_profile=profile)
```

> [!IMPORTANT]
> **한 프로파일 = 폰 한 대.** 실행할 때마다 다른 기기인 척하는 것이 오히려
> 부자연스럽습니다. `profile.id`와 `profile.android_id`를 함께 저장해 재사용하세요.

카탈로그에는 실재하는 (모델 × 안드로이드 버전) 조합 **100개**가 결정적으로 전개돼
있습니다. 전부 소스로 확인된 한국 자급제(`SM-…N`) 모델이고, 안드로이드 버전과
빌드ID 프리픽스가 정합합니다.

```python
from pykorail.device import DEVICE_PROFILES

DEVICE_PROFILES[0]
# DeviceProfile(id='s20-a13', marketing='Galaxy S20', model='SM-G981N',
#               android='13', build_id='TP1A.220624.014')
```

`model` · `android` · `build_id` 세 필드만 있으면 직접 만든 객체도 주입됩니다
(`DeviceProfileLike` 프로토콜).
선택적으로 `android_id` 필드를 제공하면 서명에도 그 값을 사용합니다. 없으면
클라이언트 생성 시 한 번 합성 ID를 생성합니다. 기본 `DeviceProfile`에는 이 필드가
자동으로 채워지며, `repr`에서는 숨겨집니다. `dataclasses.asdict(profile)`로 전체를
저장하고 `DeviceProfile(**saved_data)`로 복원할 수도 있습니다.

합성 ID는 Android 14의 `SettingsProvider.generateSsaidLocked`와 같이 임의
32바이트 사용자 키와 코레일 앱의 공개 서명 인증서로 HMAC-SHA256을 계산해 만듭니다.
실제 Android에서 발급받은 값은 아닙니다. 프로파일의 `id`만 저장하면 모델·OS는
복원되지만 `android_id`는 다음 프로세스에서 달라집니다. 라이브러리는 자동 파일
저장을 하지 않습니다.

프로파일 없이 사용할 때도 `client.android_id`를 저장하고
`Korail(android_id=saved_android_id)` 또는 `Korail.logged_in(..., android_id=saved_android_id)`로
복원할 수 있습니다. `android_id`는 프로파일 동등성·해시에 포함되므로 같은 모델·OS라도
ID가 다르면 서로 다른 가상 기기입니다. `DeviceProfile(...)`과 `profile_by_id(..., android_id=...)`는
ID 형식이 잘못되면 `ValueError`를 발생시킵니다. 후자는 프로파일을 찾은 경우에만 검증합니다.

## NetFunnel 대기열

`NetFunnelHelper` 는 클라이언트에 자동으로 엮여 있지 **않습니다 — 의도된 것입니다.**
코레일톡+ 앱은 열차 조회 · 예약 · 내 예약 조회 · 결제 전에 대기열을 통과하지만,
지금까지 본 캡처에서 통과 키가 스마트 요청(`smart.letskorail.com`)에 실린 적은
없습니다 — 서버가 통과 여부를 검사한다는 근거가 없어, 필요 없는 상황에서 매 요청마다
외부 게이트를 때리면 비용과 실패 지점만 늘어납니다.

명절 예매처럼 대기열이 실제로 붙는 상황을 만나면 직접 꺼내 쓰세요. `run()` 은 동작
(`aid`)을 받고, 기본값은 열차 조회(`act_8`)입니다.

```python
from pykorail import NetFunnelHelper, NetFunnelAction

with NetFunnelHelper() as nf:
    key = nf.run()  # 열차 조회 대기열, 통과할 때까지 블로킹
    pay_key = nf.run(NetFunnelAction.PAY)  # 결제는 다른 대기열이라 따로 통과
```

동작과 `aid` 는 다음과 같습니다. 값은 코레일톡+ 7.0.8 의 `NetworkConstants$Netfunnel`
상수를 AlienGuard 복호 결과로 옮긴 것입니다(암호문·호출 지점 근거는
`docs/protocol-evidence-7.0.8.json` 의 `netfunnel.actions`, 7.1.0 에서 생긴 `act_14_2` 는
`docs/protocol-evidence-7.1.0.json`).

| 동작 | 상수 | `aid` |
|---|---|---|
| 열차 조회 (평시) | `NetFunnelAction.TRAIN_SEARCH` | `act_8` |
| 열차 조회 (성수기) | `NetFunnelAction.TRAIN_SEARCH_PEAK` | `act_8_2` |
| 열차 조회 (할인상품) | `NetFunnelAction.TRAIN_SEARCH_SPECIAL_OFFER` | `act_6` |
| 예약 (평시) | `NetFunnelAction.RESERVE` | `act_14` |
| 예약 (성수기) | `NetFunnelAction.RESERVE_PEAK` | `act_14_2` |
| 결제 | `NetFunnelAction.PAY` | `act_18` |
| 내 예약 조회 | `NetFunnelAction.RESERVATION_VIEW` | `act_21` |

열차 조회에서 세 값 중 무엇을 쓸지는 앱(`TrainScheduleViewModel.netFunnelTrainSchedule`)
에 따르면 다음 규칙으로 정해집니다.

1. 할인상품(`SpecialOffer`)을 골랐고 그것이 `ACCOMPANY_4` 가 아니면 `act_6`.
2. 관광열차(`trainGroup.tour`)면 대기열을 거치지 않습니다(빈 `aid`).
3. 그 밖에는 `schedule.runDt` 응답의 출발일 항목 성수기 플래그가 참이면 `act_8_2`,
   아니면 `act_8` 입니다. 플래그는 `bizDdStgCd == "5"` 이고, 그 밖의 값(`1`–`4`)과
   조회일 항목이 없을 때는 `act_8` 입니다. 그 판정은
   [`korail.trains.run_dates()`](#운행-달력-조회) 로 운행 달력을 받아
   `netfunnel_action_for()` 에 넘기면 됩니다.

예약은 7.1.0 부터 앱(`NetFunnelHelper.reserveNetFunnelActionId`)이 첫 여정의 운행일
(`txtRunDt`, 비었으면 `txtDptDt`)로 같은 성수기 판정을 해 `act_14_2` 또는 `act_14` 를
고릅니다 — `netfunnel_action_for(calendar, train.run_date or train.dep_date, action=NetFunnelAction.RESERVE)`
가 그 판정입니다. 열차 조회와 달리 출발일이 아니라 운행일입니다.

비동기 코드에서는 `AsyncNetFunnelHelper` 를 `await` 합니다. 리소스와 달리
`AsyncKorail` 에 엮여 있지 않은 것은 동기판과 같습니다.

```python
from pykorail import AsyncNetFunnelHelper, NetFunnelAction

async with AsyncNetFunnelHelper() as nf:
    key = await nf.run(NetFunnelAction.TRAIN_SEARCH_PEAK)
```

두 헬퍼 모두 선택적 `device_profile` 을 받습니다. 넘기면 User-Agent 의 모델 · OS ·
빌드가 그 프로파일을 따르고, 생략하면 DynaPath 기본값과 같은 카탈로그 프로파일
(`s24ultra-a14`)을 씁니다. 코레일 클라이언트와 같은 가상 기기로 보이게 하려면
`korail.device_profile` 을 넘기세요.

```python
async with AsyncNetFunnelHelper(device_profile=korail.device_profile) as nf:
    key = await nf.run()
```

컨텍스트 매니저로 나가면 `close()` 가 연 HTTP 세션을 정리합니다. 이중 `close()` 는
조용히 넘어갑니다.

제약:

- `AsyncNetFunnelHelper` 는 asyncio 전용이고 `curl_cffi` 가 필요합니다 — 동기판에는
  requests 폴백이 있지만 비동기판에는 없습니다.
- 캐시는 동작(`aid`)별로 나뉩니다. `act_8` 로 받은 티켓을 결제(`act_18`)에 재사용하지
  않습니다. `clear()` 는 전부, `clear(aid)` 는 그 칸만 비우고, 한 동작이 실패하면
  실패한 칸만 비웁니다 — 결제 대기열 실패가 조회 티켓을 날리지 않습니다.
- `aid` 는 `NetFunnelActionCode`(`Literal`)로 정적으로만 검사합니다. 잘못된 문자열을
  넘겨도 런타임에는 막지 않습니다.
- 한 인스턴스를 여러 코루틴이 동시에 쓰면 `run()` 이 각자 게이트를 통과합니다. 캐시는
  **통과를 마친** 티켓만 공유하므로, 대기 중에 끼어든 호출이 미완성 티켓을 빌려 오는
  일은 없습니다. 대신 그만큼 대기열을 여러 번 때립니다.
- 비동기 인스턴스는 처음 쓴 이벤트 루프에 묶입니다. 다른 이벤트 루프에서 다시 쓰면
  `attached to a different loop` 오류가 납니다.

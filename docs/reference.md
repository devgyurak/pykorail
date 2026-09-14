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
)
```

| 인자 | 설명 |
| --- | --- |
| `verbose` | 요청·응답 본문을 `DEBUG` 로그로 남깁니다. **개인정보가 찍히니 운영에서 켜지 마세요.** |
| `device_profile` | User-Agent 와 DynaPath 서명을 함께 바꿉니다. [기기 프로파일](#기기-프로파일) 참조. |
| `validate_stations` | `trains.search` 전에 역 이름을 검증합니다. 끄면 역 마스터 조회 1회를 아낍니다. |

| 메서드 · 속성 | 반환 | 설명 |
| --- | --- | --- |
| `Korail.logged_in(id, pw, *, verbose=False, device_profile=None, validate_stations=True)` | `Korail` | 생성 + 로그인. 실패하면 연결을 닫고 예외를 던집니다. |
| `login(korail_id, korail_pw)` | `bool` | 성공 `True`, 자격증명 불일치 `False`. |
| `logout()` | `None` | **서버 세션만** 끊습니다. HTTP 연결은 살아 있어 재로그인할 수 있습니다. |
| `close()` | `None` | HTTP 연결 정리. `with` 문이 자동 호출합니다. |
| `logined` | `bool` | 로그인 상태. |
| `membership_number` · `name` · `email` · `phone_number` | `str \| None` | 로그인 후 채워집니다. |

`korail_id` 는 형태로 자동 판별합니다 — 이메일 · 휴대폰(`010-1234-5678`) · 회원번호.

> [!NOTE]
> `logout()` 과 `close()` 는 다릅니다. 로그아웃은 프로토콜 상태, 연결은 자원이라
> 수명이 다릅니다. 계정을 바꿔 다시 로그인하려면 연결이 살아 있어야 합니다.

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
> UTC 서버에서 돌려도 `datetime(2026, 4, 1, 9)` 는 한국시간 오전 9시입니다.

### `korail.reservations`

| 메서드 | 반환 | 설명 |
| --- | --- | --- |
| `all()` | `list[Reservation]` | 결제 전 예약 전체. 좌석 상세까지 채워 옵니다. |
| `find(rsv_id)` | `Reservation \| None` | 예약번호로 하나. 찾으면 요청 **2회**(목록 + 그 예약의 좌석), 목록에 없으면 1회, `rsv_id` 가 비어 있으면 0회. |
| `create(train, passengers=None, option=GENERAL_FIRST)` | `Reservation` | 예매. 좌석이 없고 예약대기가 열려 있으면 대기를 겁니다. |
| `seats(rsv_id)` | `tuple[list[Seat], str \| None]` | 좌석 상세와 발매창구 번호. |
| `pay(reservation, card)` | `None` | 카드 결제. |
| `cancel(reservation)` | `None` | 예약 취소. |

> [!IMPORTANT]
> `all()` 은 예약 하나마다 좌석 상세를 추가 조회합니다. 예약이 N개면 요청이 N+1회
> 나가니, 반복문 안에서 부르지 말고 한 번 받아 재사용하세요.
> **예약 하나만 필요하면 `find()`** 를 쓰세요 — 일치하는 예약이 있으면 목록 1회 + 그 예약의
> 좌석 1회로 끝나고, 없으면 목록 조회 1회에서 멈춥니다.

`create()` 는 예매 직후 예약을 다시 조회해 돌려줍니다 — 반환된 `Reservation` 은
`seats` 와 `wct_no` 가 채워져 있어 바로 `pay()` 에 넘길 수 있습니다.

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

| 메서드 · 속성 | 반환 | 설명 |
| --- | --- | --- |
| `has_seat()` | `bool` | 특실 또는 일반실 좌석 있음 |
| `has_special_seat()` · `has_general_seat()` | `bool` | 각각 |
| `has_waiting_list()` | `bool` | 예약대기 가능 |
| `duration_minutes` | `int \| None` | 소요 시간(분). 자정을 넘기면 보정됩니다. |
| `duration_text` | `str \| None` | 사람이 읽는 소요 시간 (`"3시간 30분"`). 1시간 미만이면 `"45분"`. |
| `summary()` | `str` | 좌석 정보를 뺀 한 줄 요약 |

### `Reservation`

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `train` | `Train` | **참조** — `reservation.train.dep_name` |
| `rsv_id` | `str` | 예약번호 (PNR) |
| `price` | `int` | 결제 예정 금액 |
| `seat_no_count` | `int` | 좌석 수 |
| `seats` | `tuple[Seat, ...]` | 배정 좌석 |
| `wct_no` | `str \| None` | 발매창구 번호 — 결제에 필요 |
| `buy_limit_date` · `buy_limit_time` | `str` | 구입기한 |
| `is_waiting` | `bool` (속성) | 예약대기 여부 |

### `Ticket`

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `train` | `Train` | **참조** |
| `seat_no` · `car_no` | `str` | 좌석 · 호차 |
| `price` | `int` | 결제 금액 |
| `pnr_no` | `str` | 예약번호 |
| `sale_info1`–`sale_info4` | `str` | 환불에 필요한 원권 식별자 |
| `ticket_no` | `str` (속성) | 위 4개를 하이픈으로 이은 승차권 번호 |

### `Seat`

| 필드 | 설명 |
| --- | --- |
| `car` · `seat` | 호차 · 좌석번호 |
| `seat_type` | 일반실 / 특실 |
| `passenger_type` | 어른 / 어린이 … |
| `price` · `original_price` · `discount` | 결제액 · 정가 · 할인액 |
| `is_waiting` (속성) | 좌석번호가 비어 있으면 예약대기 자리 |

### `Station`

| 필드 | 설명 |
| --- | --- |
| `code` · `name` | 역 코드 (`"0020"`) · 이름 (`"부산"`) |
| `latitude` · `longitude` | 좌표 (`float \| None`) |
| `group` | 노선 그룹 코드 — 같은 값이면 같은 노선군 |
| `major` · `is_major` (속성) | 주요역 노출 순번 · 주요역 여부 |
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

## 예외

```
PykorailError
├── KorailError            코레일이 strResult=FAIL 로 응답
│   ├── NeedToLoginError   P058
│   ├── NoResultsError     P100 · WRG000000 · WRD000061 · WRT300005
│   ├── SoldOutError       IRT010110 · ERR211161
│   └── LoginFailedError   자격증명 누락 / 암호화 키 발급 실패
├── NetFunnelError         대기열 게이트 실패
├── StationNotFoundError   요청 전 클라이언트 검증 — 역 이름이 없음
├── PastDepartureError     요청 전 클라이언트 검증 — 이미 지난 시각
└── TransportError         세션 생성 실패 / 비 JSON 응답
```

`except PykorailError` 하나로 라이브러리 유래 실패를 전부 잡을 수 있습니다.
매칭되지 않은 코드는 서버 메시지를 담은 `KorailError` 로 올라옵니다.

```python
from pykorail import KorailError, SoldOutError

try:
    reservation = korail.reservations.create(train)
except SoldOutError:
    ...  # 매진 — 다음 열차로
except KorailError as exc:
    print(exc.msg, exc.code)  # 서버 메시지와 h_msg_cd
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

User-Agent 와 DynaPath 서명이 **같은 기기**를 가리켜야 합니다. 한쪽만 바꾸면 그
불일치 자체가 탐지 신호가 되므로, 프로파일을 통째로 주입해 함께 바뀌게 하세요.

```python
from pykorail import Korail
from pykorail.device import profile_by_id, random_profile

# 최초 1회만 뽑아 id 를 저장하고, 그 뒤로는 계속 같은 프로파일을 씁니다.
profile = profile_by_id(saved_id) or random_profile()
save(profile.id)

korail = Korail(device_profile=profile)
```

> [!IMPORTANT]
> **한 프로파일 = 폰 한 대.** 실행할 때마다 다른 기기인 척하는 것이 오히려
> 부자연스럽습니다. 한 번 뽑은 `profile.id` 를 저장해 재사용하세요.

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

## NetFunnel 대기열

`NetFunnelHelper` 는 클라이언트에 자동으로 엮여 있지 **않습니다 — 의도된 것입니다.**
대기열은 코레일 웹 프런트가 통과하는 관문이고, 이 패키지가 쓰는 스마트 앱
엔드포인트(`smart.letskorail.com`)는 그 뒤에 있지 않습니다. 필요 없는 상황에서 매
요청마다 외부 게이트를 때리면 비용과 실패 지점만 늘어납니다.

명절 예매처럼 앱 경로에도 대기열이 붙는 상황을 만나면 직접 꺼내 쓰세요.

```python
from pykorail import NetFunnelHelper

key = NetFunnelHelper().run()  # 통과할 때까지 블로킹
```

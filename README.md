<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/devgyurak/pykorail/main/.github/assets/banner-dark.png">
  <img src="https://raw.githubusercontent.com/devgyurak/pykorail/main/.github/assets/banner-light.png" alt="pykorail — 파이썬으로 KTX 표를 조회하고 예매합니다">
</picture>

코레일 스마트 예매(코레일톡) API 를 감싼 비공식 클라이언트

[![CI](https://github.com/devgyurak/pykorail/actions/workflows/ci.yml/badge.svg)](https://github.com/devgyurak/pykorail/actions/workflows/ci.yml)
[![Coverage](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/devgyurak/pykorail/badges/coverage.json)](https://github.com/devgyurak/pykorail/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/pykorail?color=3775A9&logo=pypi&logoColor=white&cacheSeconds=10800)](https://pypi.org/project/pykorail/)
[![Python](https://img.shields.io/pypi/pyversions/pykorail?color=3776AB&logo=python&logoColor=white&cacheSeconds=10800)](https://pypi.org/project/pykorail/)
[![License](https://img.shields.io/badge/license-MIT%20%EA%B8%B0%EB%B0%98%20%C2%B7%20%EC%83%81%EC%97%85%EC%A0%81%20%EC%9D%B4%EB%93%9D%20%EA%B8%88%EC%A7%80-orange)](LICENSE)

[문서 사이트](https://pykorail.devgyurak.com) · [빠른 시작](#빠른-시작) · [할 수 있는 것](#할-수-있는-것) · [API 레퍼런스](docs/reference.md) · [기여하기](CONTRIBUTING.md)

</div>

---

## 빠른 시작

```bash
pip install pykorail
```

```python
from datetime import datetime, timedelta, timezone
from pykorail import Korail

kst = timezone(timedelta(hours=9))
# 내일 오전 9시(KST) 출발을 찾습니다.
departure = (datetime.now(kst) + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)

with Korail.logged_in("me@example.com", "password") as korail:
    trains = korail.trains.search("서울", "부산", depart_after=departure)
    for train in trains:
        print(train)
```

```text
[KTX 101]  04/01 09:00~12:30  서울~부산  특실 가능, 일반실 가능 (3시간 30분)
[KTX 103]  04/01 10:00~13:30  서울~부산  특실 매진, 일반실 가능 (3시간 30분)
[KTX 105]  04/01 11:00~14:35  서울~부산  특실 가능, 일반실 매진 (3시간 35분)
```

비동기로도 쓸 수 있습니다. 리소스와 시그니처가 같고, 호출만 `await` 입니다. 아래는
`async` 함수 안에서 부르는 부분만 적었습니다.

```python
from pykorail import AsyncKorail

async with await AsyncKorail.logged_in("me@example.com", "password") as korail:
    trains = await korail.trains.search("서울", "부산", depart_after=departure)
```

asyncio 전용이고 `curl_cffi` 가 필요합니다. 이벤트 루프·동시성 같은 나머지 제약은
[API 레퍼런스](docs/reference.md#asynckorail)에 있습니다.

> [!CAUTION]
> **승차권 재판매 목적으로 쓰지 마세요.** pykorail 은 본인이 탈 표를 예매하기 위한
> 도구입니다. 승차권을 웃돈을 받고 상습적으로 되파는 행위는 철도사업법으로 금지되어 있고,
> 상업적 이득을 얻는 데 쓰는 것은 [라이선스](#라이선스)로도 금지됩니다.
>
> 코레일과 아무 관련 없는 **비공식** 라이브러리입니다. 문서화되지 않은 앱 API 를 쓰기
> 때문에 코레일이 앱을 바꾸면 예고 없이 멈출 수 있습니다. 이용 약관과 관련 법령을
> 지키는 것은 사용자 책임이며, 과도한 자동 요청은 계정 제재로 이어질 수 있습니다.

---

## 할 수 있는 것

### 표 예매하고 결제하기

```python
from pykorail import AdultPassenger, Card, ChildPassenger

trains = korail.trains.search(
    "서울",
    "부산",
    depart_after=departure,
    passengers=[AdultPassenger(2), ChildPassenger(1)],
)

reservation = korail.reservations.create(trains[0])
print(reservation)
# [KTX 101] … 119600원(3석), 구입기한 4월 1일 09:20

korail.reservations.pay(
    reservation,
    Card(number="1234567812345678", password="12", verify_number="900101", expire="2812"),
)
```

<details>
<summary><b>뒤쪽 열차까지 이어서 보기</b></summary>

서버는 조회 한 번에 한 쪽(보통 열 편)만 줍니다. `max_pages` 를 올리면 마지막 열차의 출발
시각부터 다시 조회해 이어 붙입니다.

```python
trains = korail.trains.search("서울", "부산", include_no_seats=True, max_pages=5)
print(len(trains), trains[-1].dep_time)
```

쪽마다 요청이 한 번씩 더 나갑니다. 새 열차가 더 없으면 그 전에 멈춥니다.

</details>

<details>
<summary><b>매진일 때 예약대기 걸기</b></summary>

```python
trains = korail.trains.search("서울", "부산", include_waiting_list=True)
waitable = [t for t in trains if not t.has_seat() and t.has_waiting_list()]

reservation = korail.reservations.create(waitable[0])
assert reservation.is_waiting
```

</details>

<details>
<summary><b>인근역에서 출발·도착하는 열차까지 보기</b></summary>

앱의 "인접역" 옵션입니다. 용산 → 대전을 찾으면 서울 → 대전 · 용산 → 서대전 편도
함께 나옵니다. 직통이 없는 구간은 이걸 켜지 않으면 조회할 방법이 없습니다.

```python
trains = korail.trains.search("용산", "대전", include_nearby_stations=True)

for train in trains:
    print(train.dep_name, "→", train.arr_name)
# 서울 → 대전 / 용산 → 서대전 / 서울 → 서대전 …

# 출발은 용산에서만 하고 싶다면 결과에서 고르면 됩니다
from_yongsan = [t for t in trains if t.dep_name == "용산"]
```

결과가 **더해지는** 것이 아니라 후보가 넓어지는 것이라, 켜면 인근역 편이 시간순으로
끼어들며 뒤쪽 직통편을 밀어낼 수 있습니다. 그래서 기본값은 꺼짐입니다.

</details>

<details>
<summary><b>환승 조회 · 예매하기</b></summary>

직통이 없는 구간은 한 번 갈아타는 여정으로 찾습니다. 조회는 로그인하지 않아도 됩니다.

```python
transfers = korail.trains.search_transfers("강릉", "목포")

for transfer in transfers:
    first, second = transfer.legs
    print(first.train_no, "→", transfer.station_name, "→", second.train_no)

first, second = korail.reservations.create_transfer(transfers[0])

print(first.rsv_id == second.rsv_id)  # True — 예약번호는 하나입니다
```

구간을 따로 `create()` 하면 첫 구간만 잡히고 둘째가 매진될 수 있습니다. 이쪽은 한 구간이라도
안 되면 서버가 통째로 거절하고, `cancel()` 은 예약번호 단위라 둘 중 어느 것을 넘겨도 두
구간이 함께 취소됩니다.

</details>

<details>
<summary><b>운임 조회</b></summary>

예약하기 전에 값을 봅니다. **로그인하지 않아도 됩니다.**

```python
train = korail.trains.search("서울", "부산")[0]

for fare in korail.trains.fares(train):
    print(fare.seat_class_name, fare.total)
# 일반실 59800
# 특실 83700
```

할인 전의 기준 운임입니다. 실제로 낼 금액은 예약한 뒤 `Reservation.price` 에 있습니다.

</details>

<details>
<summary><b>호차 · 좌석을 골라 예매하기</b></summary>

`create()` 는 좌석을 서버가 정합니다. 자리를 직접 고르려면 호차 목록 다음에 좌석 배치를
받아 `create_with_seats()` 에 넘깁니다. **둘 다 로그인이 필요합니다.**

```python
from pykorail import AdultPassenger

train = korail.trains.search("서울", "부산")[0]

# 좌석은 승객 한 명에 하나씩이라, 두 자리가 남은 호차를 고릅니다.
car = next(car for car in korail.trains.cars(train) if car.remaining_seats >= 2)
picked = [seat for seat in korail.trains.seats(train, car) if seat.is_available][:2]

reservation = korail.reservations.create_with_seats(train, picked, [AdultPassenger(2)])
```

좌석 수가 승객 수와 다르거나, 같은 좌석을 두 번 넘기거나, 객실이 섞이면 요청 전에
`ValueError` 로 막습니다.

</details>

<details>
<summary><b>내 예약·승차권 보기</b></summary>

```python
for reservation in korail.reservations.all():
    print(reservation.train.dep_name, "→", reservation.train.arr_name, reservation.price)

for ticket in korail.tickets.all():
    print(ticket.ticket_no, ticket.car_no, ticket.seat_no)
    korail.tickets.refund(ticket)  # 환불
```

</details>

<details>
<summary><b>공항버스 시간표 · 좌석 보기</b></summary>

로그인 없이 됩니다. 코레일이 파는 것은 광명역 → 인천공항(T1 · T2) 방향뿐입니다.

```python
buses = korail.airport_bus.search("광명역", "인천공항T1")
bus = next(bus for bus in buses if bus.has_seat())

print(bus, bus.price)
print([seat.seat_no for seat in korail.airport_bus.seats(bus) if seat.is_available])
```

</details>

<details>
<summary><b>마일리지 · 할인쿠폰 보기</b></summary>

```python
mileage = korail.membership.mileage()
print(mileage.total, "마일리지,", mileage.expiring, "이번 달 소멸 예정")

for entry in mileage.entries:  # 최근 30일의 적립 · 사용 내역
    print(entry.date, entry.movement, entry.amount)  # 20261003 적립 2990

for coupon in korail.membership.coupons():
    print(coupon.title, coupon.valid_until)
```

</details>

<details>
<summary><b>기기 프로파일 고정하기</b> — 여러 번 실행한다면</summary>

프로파일마다 합성 Android ID가 하나 생성되며, 같은 프로파일을 쓰는 클라이언트는
그 ID를 재사용합니다. 재시작 후에도 유지하려면 `id`와 `android_id`를 함께 저장하세요.
pykorail은 파일을 자동으로 읽거나 쓰지 않습니다.

```python
from pykorail.device import profile_by_id, random_profile

profile = profile_by_id(saved_id, android_id=saved_android_id) or random_profile()
# 호출 앱의 설정에 profile.id와 profile.android_id를 함께 저장합니다.
korail = Korail(device_profile=profile)
```

전체 프로파일을 저장하려면 `dataclasses.asdict(profile)`을 직렬화한 뒤
`DeviceProfile(**saved_data)`로 복원할 수도 있습니다. ID는 Android 14의
SSAID 계산 방식과 코레일 공개 서명 인증서로 생성한 합성 값이며, 실제 기기에서
추출한 값은 아닙니다. 프로파일을 생략하면 클라이언트마다 새 ID가 생성됩니다.
이때도 `korail.android_id`를 저장하고 `Korail(android_id=saved_android_id)`로 복원할 수 있습니다.
프로파일 유무와 무관하게 User-Agent는 `korailtalk`입니다.

</details>

---

## 알아두면 좋은 것

- **역은 이름으로** — `"서울역"` 이 아니라 `"서울"`. 오타면 요청 전에 막고 비슷한 역을 알려줍니다.
- **시각은 항상 KST** — tz 없는 `datetime` 은 실행 머신의 타임존과 무관하게 한국시간으로 해석됩니다.
- **지난 시각은 거부** — 서버가 과거에도 빈 결과만 줘서 "떠난 열차"와 "열차 없음"이 구분되지 않습니다.
- **실패는 예외로** — `cancel()` · `pay()` 는 성공 시 아무것도 반환하지 않습니다.
- **DynaPath 토큰은 선언(Flow-1) 토큰입니다** — 네이티브 코덱을 순수 파이썬으로 바이트 단위 재현해 기기 사실을 담은 `201…` 토큰을 냅니다(`.so` 불필요). 하드웨어 서명(Flow-2)은 재현하지 않으며, 서버가 그것만 허용하게 되면 깨집니다. [자세히](docs/reference.md#기기-프로파일)

```python
from pykorail import KorailError, SoldOutError

try:
    korail.reservations.create(train)
except SoldOutError:
    ...  # 매진 — 다음 열차로
except KorailError as exc:
    print(exc.msg, exc.code)  # 코레일이 준 메시지와 코드
```

---

## 문서

- 🌐 [**문서 사이트**](https://pykorail.devgyurak.com) — 이 문서들을 한곳에서: 검색 · 다크 모드
- 📖 [**API 레퍼런스**](docs/reference.md) — 전체 메서드 · 모델 · 옵션 · 예외
- 🤝 [기여 가이드](CONTRIBUTING.md) — 개발 환경, 테스트 규칙, PR 절차
- 🏛 [아키텍처 규약](AGENTS.md) — 계층 구조, 외부 API 불변식
- 🤖 [에이전트 설정](.agents/README.md) — Codex · Claude Code · Pi · Cursor · OpenCode
- 🔐 [보안 정책](SECURITY.md) · [행동 강령](CODE_OF_CONDUCT.md)


---

## 자주 묻는 것

<details>
<summary><b>로그인이 안 됩니다</b></summary>

설치할 때 경고가 떴다면 `curl_cffi` 대신 `requests` 로 돌고 있을 수 있습니다.
코레일은 TLS 지문을 보기 때문에 이때 로그인이 거부될 수 있습니다.
`pip install curl_cffi` 로 해결되는 경우가 대부분입니다.

휴대폰 번호는 `010-1234-5678`과 `01012345678` 모두 입력할 수 있습니다.
클라이언트가 휴대폰 로그인으로 분류하고 하이픈을 제거해 전송합니다.

`PasswordChangeRequiredError` 가 난다면 아이디 · 비밀번호는 맞습니다. 같은 비밀번호를
6개월 넘게 써서 코레일이 변경 안내를 띄운 상태이고, 그동안은 로그인이 끝나지 않습니다.
코레일톡 앱이나 홈페이지에서 안내를 처리한 뒤 다시 실행하세요.

</details>

<details>
<summary><b>Windows 에서 설치가 안 됩니다</b></summary>

`curl_cffi` 의 libcurl DLL 로드가 실패하는 환경이 있습니다.
`pip install "pykorail[fallback]"` 로 requests 폴백을 함께 설치하세요.
다만 위에 적은 이유로 로그인이 막힐 수 있습니다.

</details>

<details>
<summary><b>어제까지 되던 게 오늘 안 됩니다</b></summary>

코레일이 서버를 바꿨을 수 있습니다.
[API 변경 이슈](https://github.com/devgyurak/pykorail/issues/new?template=external_api_change.yml)
로 알려주시면 대응하겠습니다. **가장 도움이 되는 기여입니다.**

</details>

<details>
<summary><b>예매가 확실히 되나요?</b></summary>

이 라이브러리는 앱과 같은 요청을 보낼 뿐이고, 좌석 배정은 코레일 서버가 합니다.
명절 예매처럼 경쟁이 심한 상황에서 성공을 보장하지 않습니다.

</details>

<details>
<summary><b>프록시를 넣을 계획은 없나요?</b></summary>

없고, 앞으로도 넣지 않습니다. 프록시로 출처를 바꿔 가며 요청하는 것은 코레일 서버를
속여 정상 이용자보다 유리하게 예매하려는 부정한 방법입니다.

</details>

---

## 개발

파이썬 3.11 이상 (3.11 – 3.15 에서 테스트합니다).

```bash
uv sync --all-extras
uv run ruff format && uv run ruff check && uv run ty check && uv run pytest
```

네 개를 전부 통과해야 합니다. 커버리지 하한 90%는 `pytest` 가 강제하고, 지금 수치는
[CI](https://github.com/devgyurak/pykorail/actions/workflows/ci.yml) 에서 볼 수 있습니다.

기여를 환영합니다 — [`CONTRIBUTING.md`](CONTRIBUTING.md) 부터 보세요. 새 엔드포인트는
**공식 코레일톡+ APK 를 디컴파일해 경로와 폼 필드를 확인한 뒤에만** 추가합니다.
릴리스 절차는 [CONTRIBUTING 의 릴리스 절](CONTRIBUTING.md#릴리스-메인테이너용)에 있습니다.

---

## 라이선스

MIT 에 **상업적 이득 금지** 조항을 더한 자체 라이선스입니다. 그래서 MIT 도, OSI 기준의
오픈소스도 아닙니다.

- **금지** — 이 패키지로 확보한 승차권 · 예약을 산 값보다 비싸게 되파는 것, 수수료 · 구독료 ·
  광고 수익을 받는 예매 · 예약대기 · 표 확보 서비스, 이 패키지에 전부 또는 상당 부분 기대는
  상품 · 서비스를 파는 것
- **허용** — 본인의 여행, 다른 사람의 표를 수수료 없이 정가로 대신 예매하는 것, 단체가 소속원의
  여행에 쓰는 것, 연구 · 교육 · 비영리 개인 프로젝트

이 요약은 참고용이고 영문 [LICENSE](LICENSE) 가 우선합니다. 0.3.0 까지의 배포본은 MIT 그대로입니다.

---

<div align="center">

<sub>코레일과 무관한 비공식 프로젝트</sub>

</div>


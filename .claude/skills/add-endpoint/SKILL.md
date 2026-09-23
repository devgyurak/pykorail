---
name: add-endpoint
description: pykorail 에 새 코레일 API 엔드포인트를 추가하는 절차. "환승 조회 붙여줘", "새 엔드포인트 추가", "이 API 를 클라이언트에 넣어줘" 같은 요청에 사용하세요. 공식 코레일톡+ APK 디컴파일로 경로·폼 필드를 먼저 검증한 뒤 상수 → 모델 → 리소스 → 테스트 순서로 붙입니다.
---

# 새 엔드포인트 추가

> [!IMPORTANT]
> **APK 검증 없이 엔드포인트를 추가하지 마세요.** 이 절차의 0단계는 선택이 아닙니다.

## 왜 APK 를 봐야 하나

코레일 API 는 문서가 없습니다. 추측으로 만든 필드 이름은 **에러가 나지 않고 조용히
빈 값**이 됩니다 — `h_dpt_rs_stn_cd` 를 `h_dpt_stn_cd` 로 쓰면 서버는 "출발역 없음"
으로 처리하고 빈 결과를 돌려줍니다. 테스트는 통과하고, 사용자만 이유 없이 실패합니다.

더 나쁜 것은 **서명 대상 경로**입니다. `DYNAPATH_PATHS` 에 잘못 넣으면 불필요한
서명이 붙고, 빼먹으면 서명이 없어 거부됩니다. 둘 다 앱 동작을 봐야만 알 수 있습니다.

그래서 이 저장소의 규칙은 하나입니다: **앱이 실제로 그렇게 하는 것을 확인한 것만
코드에 넣는다.**

---

## 0. 공식 APK 디컴파일 검증 (필수)

### 0-1. APK 확보

대상은 **코레일톡+ (`com.korail.talk`)** 입니다. 본인 안드로이드 기기에 설치된
APK 를 추출하는 것이 가장 확실합니다.

```bash
# 기기가 연결돼 있을 때
adb shell pm path com.korail.talk
adb pull /data/app/.../base.apk korail.apk
```

기기가 없다면 사용자에게 APK 또는 디컴파일 결과를 요청하세요. **출처가 불분명한
미러 사이트 APK 는 변조 가능성이 있으니 쓰지 마세요.**

APK 버전을 기록해 두세요 — 나중에 "언제 확인한 것인가" 가 중요해집니다.

```bash
uvx --from androguard androguard apkid korail.apk   # package / versionName 확인
```

### 0-2. 디컴파일

```bash
# 리소스 + 스멀리 (경로 문자열은 보통 여기서 다 보입니다)
uvx --from apkleaks apktool d korail.apk -o korail_apk

# 자바 소스로 보고 싶으면
#   jadx -d korail_src korail.apk
```

`apktool`/`jadx` 가 없으면 사용자에게 설치를 요청하거나, 디컴파일된 트리를 받으세요.

### 0-3. 엔드포인트 경로 확인

이 패키지가 쓰는 경로는 전부 `com.korail.mobile.<...>` 형태입니다.

```bash
grep -rn "com\.korail\.mobile\." korail_apk/ | grep -iv "smali_classes" | sort -u | head -50
```

찾은 경로가 `constants.py` 의 기존 항목과 같은 규칙인지 확인하세요.

### 0-4. 폼 필드 이름 확인 (가장 중요)

해당 화면의 Activity/Fragment 또는 Retrofit 인터페이스에서 파라미터 이름을 뽑습니다.

```bash
# 요청 파라미터 후보
grep -rn "txt[A-Z][A-Za-z]*\|hid[A-Z][A-Za-z]*" korail_apk/smali*/com/korail/ | head -40

# 응답 필드 후보
grep -rn '"h_[a-z_]*"' korail_apk/smali*/com/korail/ | sort -u | head -40
```

**확인해야 할 것:**

- 요청 폼 필드의 **정확한 철자와 대소문자** (`txtGoAbrdDt` — `txtGoAbrdDT` 아님)
- 빈 문자열로 보내는 필드가 있는지 (앱이 그렇게 하면 우리도 그래야 합니다)
- `Device` · `Version` · `Key` · `Sid` 중 무엇을 싣는지 (엔드포인트마다 다릅니다)
- 응답 필드 이름 (`h_...`)과 중첩 구조 (`{"a_infos": {"a_info": [...]}}`)

### 0-5. 서명 대상인지 확인

DynaPath 토큰(`x-dynapath-m-token`)을 붙이는 경로는 앱이 명시적으로 고릅니다.
인터셉터나 토큰 생성 호출부를 찾아 **경로 목록**을 확인하세요.

```bash
grep -rn "dynapath\|DynaPath\|x-dynapath" korail_apk/smali*/ | head -20
```

여기서 확인된 경로만 `DYNAPATH_PATHS` 에 넣습니다. **추측으로 넣지 마세요.**

### 0-6. 근거 기록

찾은 것을 요약해 두세요. PR 본문과 코드 주석에 들어갑니다.

```
APK: com.korail.talk versionName 7.0.1 (2026-08 추출)
경로: com.korail.mobile.transfer.TransferView
  → TransferViewActivity.smali:214 에서 호출
요청: Device, Version, Key, txtTrnNo, txtDptDt
응답: {"trsf_infos": {"trsf_info": [{"h_trsf_stn_nm", "h_trsf_wait_tm"}]}}
서명: DynaPath 대상 아님 (인터셉터 경로 목록에 없음)
```

### 0-7. 확인할 수 없다면 멈추세요

APK 를 못 구했거나 필드를 확정하지 못했다면 **거기서 멈추고 그 사실을 보고하세요.**
"아마 이럴 것 같다" 로 코드를 넣지 마세요. 그건 조용히 실패하는 코드를 만드는 일이고,
나중에 원인을 찾는 데 훨씬 큰 비용이 듭니다.

로그인 없이 되는 공개 조회(역 마스터 등)는 실제 호출로 응답 모양을 확인할 수
있습니다. 그 경우에도 **요청 폼 필드는 APK 로 확인**해야 합니다.

---

## 1. 엔드포인트 상수

`src/pykorail/constants.py` 의 `API_ENDPOINTS` 에 추가합니다.

```python
"transfer": f"{KORAIL_MOBILE}.transfer.TransferView",
```

0-5 에서 **서명 대상으로 확인됐을 때만** `DYNAPATH_PATHS` 에도 추가합니다.

## 2. 모델 (응답이 구조화돼 있다면)

`src/pykorail/models/<이름>.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pykorail.models.parsing import integer, text


@dataclass(frozen=True)
class Transfer:
    """환승 정보 한 건."""

    station_name: str
    wait_minutes: int

    @classmethod
    def from_response(cls, data: dict[str, Any]) -> Transfer:
        return cls(
            station_name=text(data, "h_trsf_stn_nm"),
            wait_minutes=integer(data, "h_trsf_wait_tm"),
        )
```

지켜야 할 것:
- `frozen=True` 이고 `from_response()` 로만 만듭니다.
- `data.get(...)` 을 날로 쓰지 말고 `text`/`integer`/`floating` 을 쓰세요 —
  코레일은 필드를 빼먹거나 빈 문자열로 보냅니다.
- 다른 모델을 참조한다면 **상속이 아니라 필드로** 담으세요 (`train: Train`).
- `models/__init__.py` 와 필요하면 `pykorail/__init__.py` 의 `__all__` 에 추가.

## 3. 리소스 메서드

**`client.py` 에 붙이지 마세요.** 도메인에 맞는 리소스를 고르거나 새로 만듭니다.

```python
def transfers(self, train: Train) -> list[Transfer]:
    """환승 정보를 조회합니다.

    폼 필드는 코레일톡+ 7.0.1 의 TransferViewActivity 에서 확인했습니다.

    Raises:
        NoResultsError: 환승 구간이 없습니다.
    """
    url = API_ENDPOINTS["transfer"]
    headers, _ = self._api.sign(url)  # 서명 대상이 아니면 ({}, None)
    payload = self._api.get(
        url,
        params={**self._api.base_payload(), "txtTrnNo": train.train_no},
        headers=headers,
    )
    self._api.check(payload)

    return [Transfer.from_response(i) for i in payload.get("trsf_infos", {}).get("trsf_info", [])]
```

지켜야 할 것:
- HTTP 는 `self._api` 를 통해서만. `_session` 을 직접 만지지 마세요.
- 응답 검사는 `self._api.check(payload)`.
- "결과 없음"을 빈 리스트로 다루려면 `except NoResultsError: return []`.
- 상태를 바꾸는 메서드는 `-> None` 이고 실패 시 예외를 던집니다. 불리언 금지.
- 부속 데이터가 필요하면 **먼저 조회해서 생성자에 넘기세요.**
- **APK 근거를 docstring 이나 주석에 한 줄 남기세요.** 다음 사람이 "이 이상한 필드
  왜 있지" 하고 지우는 것을 막습니다.

새 리소스라면 `resources/__init__.py` 에 등록하고 `Korail.__init__` 에서 배선합니다.

## 4. 테스트

`tests/payloads.py` 에 **APK 에서 확인한 모양 그대로** 응답 샘플을 추가하고,
`tests/conftest.py` 의 `korail` 픽스처 `routes` 에 엔드포인트를 등록하세요.

```python
class TestTransfers:
    def test_parses_transfers(self, korail) -> None:
        # given
        client, _ = korail
        train = client.trains.search("서울", "부산")[0]

        # when
        transfers = client.trains.transfers(train)

        # then
        assert [t.station_name for t in transfers] == ["대전"]

    def test_sends_exact_form_fields(self, korail) -> None:
        """폼 필드 이름이 바뀌면 서버가 조용히 빈 결과를 줍니다."""
        # given
        client, session = korail
        train = client.trains.search("서울", "부산")[0]

        # when
        client.trains.transfers(train)

        # then
        params = session.kwargs_for("transfer")["params"]
        assert params["txtTrnNo"] == "101"
        assert set(params) == {"Device", "Version", "Key", "txtTrnNo"}

    def test_empty_when_no_results(self, make_korail) -> None:
        # given
        client, _ = make_korail({"transfer": NO_RESULTS})

        # when
        transfers = client.trains.transfers(...)

        # then
        assert transfers == []
```

**`# when` 과 `# then` 은 필수, `# given` 은 준비 코드가 있을 때만 씁니다** —
`tests/test_style.py` 가 강제합니다. 픽스처나 `parametrize` 입력만 받고 바로
실행하는 테스트에 빈 Given 을 얹지 마세요. 그건 규약 준수가 아니라 잡음입니다
(AGENTS.md §5.2).

`set(params)` 로 **전체 필드 집합**을 고정하는 테스트를 꼭 하나 넣으세요 — 나중에
누가 필드를 지우거나 이름을 바꾸면 그때 잡힙니다.

**테스트에 `if`/`for`/`while` 문을 쓰지 마세요** — `tests/test_style.py` 가 강제합니다.

## 5. 마무리

```bash
uv run ruff format && uv run ruff check --fix && uv run ty check && uv run pytest
```

커버리지 90% 하한을 넘겨야 합니다. `docs/reference.md` 의 API 표에도 한 줄 추가하고,
PR 본문의 "외부 API 영향" 절에 **0-6 의 APK 근거를 그대로 붙여넣으세요.**

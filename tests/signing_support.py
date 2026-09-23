"""잠금 진입 순서를 결정적으로 뒤집는 동시성 테스트 지원 도구입니다."""

from __future__ import annotations

from threading import Event, Lock


class ReverseFirstTwoLock:
    """첫 호출을 두 번째 호출의 잠금 해제까지 대기시킵니다. sleep을 쓰지 않습니다."""

    def __init__(self) -> None:
        self.first_waiting = Event()
        self._finished = Event()
        self._counter_lock = Lock()
        self._lock = Lock()
        self._entries = 0

    def __enter__(self) -> None:
        with self._counter_lock:
            entry = self._entries
            self._entries += 1
        if entry == 0:
            self.first_waiting.set()
            assert self._finished.wait(2), "두 번째 호출이 잠금을 해제하지 않았습니다"
        self._lock.acquire()

    def __exit__(self, *args: object) -> None:
        self._lock.release()
        self._finished.set()

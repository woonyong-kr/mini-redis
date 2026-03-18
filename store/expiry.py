"""
TTL / 만료 관리 (팀원 B 담당)

키의 만료 시간을 관리합니다.
각 메서드를 구현하세요. 메서드 이름과 파라미터는 변경하지 마세요.
"""

import asyncio
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from store.datastore import DataStore


class ExpiryManager:
    """
    TTL 기반 키 만료 관리자.

    내부 구조:
      self._expiry: dict  - 만료 시각 저장
                            {"key": expiry_timestamp} 형태
                            expiry_timestamp = time.time() + seconds
    """

    def __init__(self, store: "DataStore"):
        self._store = store
        self._expiry: dict = {}
        self._store.bind_expiry_manager(self)

    def set_expiry(self, key: str, seconds: float) -> None:
        """
        키의 만료 시간을 설정합니다.
        hints: time.time() + seconds를 만료 timestamp로 저장
        """
        self._expiry[key] = time.time() + seconds

    def get_ttl(self, key: str) -> float:
        """
        키의 남은 TTL(초)을 반환합니다.
        반환값:
          - 양수: 남은 초
          - -1: 만료 시간이 없는 키 (영구 저장)
          - -2: 키가 존재하지 않음
        힌트: time.time()으로 현재 시각을 구하고 차이를 계산
        """
        if not self._store.exists(key):
            self._expiry.pop(key, None)
            return -2

        expiry_at = self._expiry.get(key)
        if expiry_at is None:
            return -1

        remaining = expiry_at - time.time()
        if remaining <= 0:
            self._store.delete(key)
            return -2
        return remaining

    def is_expired(self, key: str) -> bool:
        """
        키가 만료되었는지 확인합니다.
        만료 시각이 없으면 False를 반환합니다.
        힌트: key가 _expiry에 없으면 False, 있으면 time.time() 비교
        """
        expiry_at = self._expiry.get(key)
        if expiry_at is None:
            return False
        if key not in self._store._data:
            self._expiry.pop(key, None)
            return False
        return time.time() >= expiry_at

    def remove_expiry(self, key: str) -> None:
        """
        키의 만료 설정을 제거합니다. (PERSIST 명령어용)
        힌트: _expiry에서 key를 pop (없어도 에러 없게)
        """
        self._expiry.pop(key, None)

    def on_key_deleted(self, key: str) -> None:
        """
        키가 삭제될 때 호출됩니다. 만료 정보도 함께 제거합니다.
        DataStore.delete()에서 이 메서드를 호출해야 합니다.
        """
        self.remove_expiry(key)

    async def active_expiry_loop(self) -> None:
        """
        백그라운드에서 주기적으로 만료된 키를 청소합니다.
        server.py에서 asyncio.create_task()로 실행됩니다.

        구현 방법:
          while True:
              만료된 키들을 찾아서 삭제
              await asyncio.sleep(0.1)  # 0.1초마다 실행
        """
        while True:
            expired_keys = [
                key for key, expiry_at in list(self._expiry.items())
                if time.time() >= expiry_at
            ]
            for key in expired_keys:
                self._store.delete(key)
            await asyncio.sleep(0.1)

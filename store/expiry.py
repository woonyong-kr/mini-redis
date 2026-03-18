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

    def __init__(self, store: "DataStore", interval_seconds: float = 0.1):
        self._store = store
        # 키 → 만료될 유닉스 타임스탬프 (float)
        self._expiry: dict[str, float] = {}
        self._interval_seconds = interval_seconds
        self._store.register_delete_hook(self.on_key_deleted)

    def set_expiry(self, key: str, seconds: float) -> None:
        """
        키의 만료 시간을 설정합니다.
        현재 시각에 seconds를 더해 만료 타임스탬프로 저장합니다.
        """
        self._expiry[key] = time.time() + seconds

    def get_ttl(self, key: str) -> float:
        """
        키의 남은 TTL(초)을 반환합니다.
        반환값:
          - 양수: 남은 초
          - -1: 만료 시간이 없는 키 (영구 저장)
          - -2: 키가 존재하지 않음
        """
        # 키 자체가 없으면 -2
        if not self._store.exists(key):
            return -2
        # 만료 설정이 없으면 -1 (영구 저장)
        if key not in self._expiry:
            return -1
        # 남은 시간 계산
        remaining = self._expiry[key] - time.time()
        # 이미 만료됐으면 Lazy 삭제 처리 후 -2 반환
        if remaining <= 0:
            self._store.delete(key)
            del self._expiry[key]
            return -2
        return remaining

    def is_expired(self, key: str) -> bool:
        """
        키가 만료되었는지 확인합니다.
        만료 시각이 없으면 False를 반환합니다.
        """
        # 만료 설정이 없으면 만료되지 않음
        if key not in self._expiry:
            return False
        # 현재 시각이 만료 시각보다 크거나 같으면 만료됨
        return time.time() >= self._expiry[key]

    def remove_expiry(self, key: str) -> None:
        """
        키의 만료 설정을 제거합니다. (PERSIST 명령어용)
        키가 없어도 에러 없이 무시합니다.
        """
        self._expiry.pop(key, None)

    def on_key_deleted(self, key: str) -> None:
        """
        키가 삭제될 때 호출됩니다. 만료 정보도 함께 제거합니다.
        DataStore.delete()에서 이 메서드를 호출해야 합니다.
        """
        self._expiry.pop(key, None)

    async def active_expiry_loop(self) -> None:
        """
        백그라운드에서 주기적으로 만료된 키를 청소합니다.
        server.py에서 asyncio.create_task()로 실행됩니다.

        0.1초마다 _expiry를 순회하며 만료된 키를 삭제합니다.
        dict를 순회하면서 동시에 수정하면 오류가 발생하므로
        먼저 만료 키를 수집한 뒤 일괄 삭제합니다.
        """
        while True:
            now = time.time()

            # 만료된 키 수집 (순회 중 dict 수정 방지를 위해 리스트로 복사)
            expired_keys = [
                key for key, exp_at in list(self._expiry.items())
                if now >= exp_at
            ]

            # 수집된 키 일괄 삭제
            for key in expired_keys:
                self._store.delete(key)
                self._expiry.pop(key, None)

            # 0.1초 대기 후 반복
            await asyncio.sleep(self._interval_seconds)

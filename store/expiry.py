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
      self._expiry: dict
        {"key": expiry_timestamp} 형태
    """

    def __init__(self, store: "DataStore", interval_seconds: float = 0.1):
        self._store = store
        self._expiry: dict[str, float] = {}
        self._interval_seconds = interval_seconds
        self._store.bind_expiry_manager(self)
        self._store.register_delete_hook(self.on_key_deleted)

    def set_expiry(self, key: str, seconds: float) -> None:
        self._expiry[key] = time.time() + seconds

    def get_ttl(self, key: str) -> float:
        if not self._store.exists(key):
            return -2
        if key not in self._expiry:
            return -1

        remaining = self._expiry[key] - time.time()
        if remaining <= 0:
            self._store.delete(key)
            return -2
        return remaining

    def is_expired(self, key: str) -> bool:
        if key not in self._expiry:
            return False
        return time.time() >= self._expiry[key]

    def remove_expiry(self, key: str) -> None:
        self._expiry.pop(key, None)

    def on_key_deleted(self, key: str) -> None:
        self._expiry.pop(key, None)

    async def active_expiry_loop(self) -> None:
        while True:
            now = time.time()
            expired_keys = [
                key for key, expiry_at in list(self._expiry.items())
                if now >= expiry_at
            ]
            for key in expired_keys:
                self._store.delete(key)
            await asyncio.sleep(self._interval_seconds)

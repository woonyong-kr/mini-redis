"""
인메모리 데이터 스토어 (팀원 B 담당)

모든 키-값 데이터를 메모리에 저장하고 관리합니다.
각 메서드를 구현하세요. 메서드 이름과 파라미터는 변경하지 마세요.
"""

from __future__ import annotations

import fnmatch
from collections import deque
from typing import Optional, Any, List, Callable

from store.hash_table import Hash
from store.redis_object import (
    RedisObject,
    TYPE_STRING, TYPE_HASH, TYPE_LIST, TYPE_SET, TYPE_ZSET, TYPE_NONE,
    make_list,
)


class DataStore:
    """
    인메모리 키-값 스토어.

    내부 구조:
      self._data: dict
        {"key": RedisObject} 형태
        hash 타입의 RedisObject.value는 커스텀 Hash를 사용한다.
    """

    def __init__(self):
        self._data: dict[str, RedisObject] = {}
        self._delete_hooks: list[Callable[[str], None]] = []
        self._expiry_manager = None

    # ─────────────────────────────────────────
    # 범용 메서드
    # ─────────────────────────────────────────

    def register_delete_hook(self, hook: Callable[[str], None]) -> None:
        """키 삭제 시 호출할 훅을 등록합니다."""
        self._delete_hooks.append(hook)

    def bind_expiry_manager(self, expiry_manager) -> None:
        """만료 확인용 ExpiryManager를 연결합니다."""
        self._expiry_manager = expiry_manager

    def _purge_if_expired(self, key: str) -> None:
        if self._expiry_manager is None:
            return
        if self._expiry_manager.is_expired(key):
            self.delete(key)

    def get(self, key: str) -> Optional[RedisObject]:
        """
        키에 저장된 RedisObject를 반환합니다.
        키가 없으면 None을 반환합니다.
        """
        self._purge_if_expired(key)
        return self._data.get(key)

    def set(self, key: str, obj: RedisObject) -> None:
        """
        키에 RedisObject를 저장합니다.
        기존 값이 있으면 덮어씁니다.
        """
        self._data[key] = obj

    def delete(self, key: str) -> int:
        """
        키를 삭제합니다.
        반환: 삭제된 키의 수 (1 또는 0)
        """
        if key in self._data:
            del self._data[key]
            for hook in self._delete_hooks:
                hook(key)
            return 1
        return 0

    def delete_many(self, keys: List[str]) -> int:
        """
        여러 키를 삭제합니다.
        반환: 실제로 삭제된 키의 수
        """
        count = 0
        for key in keys:
            count += self.delete(key)
        return count

    def exists(self, key: str) -> bool:
        """
        키의 존재 여부를 반환합니다.
        """
        self._purge_if_expired(key)
        return key in self._data

    def get_type(self, key: str) -> str:
        """
        키에 저장된 값의 Redis 타입을 반환합니다.
        반환값: "string" | "hash" | "list" | "set" | "zset" | "none"
        """
        self._purge_if_expired(key)
        obj = self._data.get(key)
        if obj is None:
            return TYPE_NONE
        return obj.type

    def keys(self, pattern: str = "*") -> List[str]:
        """
        패턴에 매칭되는 키 목록을 반환합니다.
        pattern="*" 이면 전체 키를 반환합니다.
        """
        for key in list(self._data.keys()):
            self._purge_if_expired(key)

        if pattern == "*":
            return list(self._data.keys())
        return [key for key in self._data if fnmatch.fnmatch(key, pattern)]

    def flush(self) -> None:
        """
        모든 데이터를 삭제합니다. (FLUSHALL)
        """
        keys = list(self._data.keys())
        self._data.clear()
        for key in keys:
            for hook in self._delete_hooks:
                hook(key)

    # ─────────────────────────────────────────
    # Hash 전용 메서드
    # ─────────────────────────────────────────

    def _get_hash_table(self, key: str) -> Optional[Hash]:
        obj = self.get(key)
        if obj is None:
            return None
        if obj.type != TYPE_HASH:
            raise TypeError("WRONGTYPE Operation against a key holding the wrong kind of value")

        if isinstance(obj.value, Hash):
            return obj.value

        # 원격 dev의 dict 기반 hash와도 호환되도록 lazy migration 지원
        migrated = Hash()
        if isinstance(obj.value, dict):
            for field, value in obj.value.items():
                migrated.set(field, value)
        obj.value = migrated
        obj.encoding = "hashtable"
        return migrated

    def hget(self, key: str, field: str) -> Optional[str]:
        """Hash에서 특정 필드의 값을 반환합니다."""
        hash_value = self._get_hash_table(key)
        if hash_value is None:
            return None
        return hash_value.get(field)

    def hset(self, key: str, field: str, value: str) -> int:
        """
        Hash에 필드를 설정합니다.
        반환: 새로 추가된 필드면 1, 업데이트면 0
        """
        hash_value = self._get_hash_table(key)
        if hash_value is None:
            hash_value = Hash()
            self._data[key] = RedisObject(TYPE_HASH, "hashtable", hash_value)
        return 1 if hash_value.set(field, value) else 0

    def hdel(self, key: str, *fields: str) -> int:
        """Hash에서 필드를 삭제합니다. 반환: 삭제된 수"""
        hash_value = self._get_hash_table(key)
        if hash_value is None:
            return 0

        deleted = 0
        for field in fields:
            if hash_value.delete(field):
                deleted += 1

        if len(hash_value) == 0:
            self.delete(key)

        return deleted

    def hgetall(self, key: str) -> dict:
        """Hash의 모든 필드와 값을 반환합니다."""
        hash_value = self._get_hash_table(key)
        if hash_value is None:
            return {}
        return {field: value for field, value in hash_value.items()}

    def hexists(self, key: str, field: str) -> bool:
        """Hash에 필드가 존재하는지 확인합니다."""
        hash_value = self._get_hash_table(key)
        if hash_value is None:
            return False
        return hash_value.contains(field)

    # ─────────────────────────────────────────
    # List 전용 메서드
    # ─────────────────────────────────────────

    def lpush(self, key: str, *values: str) -> int:
        """
        List 왼쪽에 값을 추가합니다.
        반환: 추가 후 리스트 길이
        """
        obj = self.get(key)
        if obj is None:
            obj = make_list()
            self._data[key] = obj

        dq = obj.value
        for value in values:
            dq.appendleft(value)
        return len(dq)

    def rpush(self, key: str, *values: str) -> int:
        """
        List 오른쪽에 값을 추가합니다.
        반환: 추가 후 리스트 길이
        """
        obj = self.get(key)
        if obj is None:
            obj = make_list()
            self._data[key] = obj

        dq = obj.value
        for value in values:
            dq.append(value)
        return len(dq)

    def lpop(self, key: str) -> Optional[str]:
        """List 왼쪽에서 값을 꺼냅니다. 비어있으면 None."""
        obj = self.get(key)
        if obj is None:
            return None

        dq = obj.value
        if not dq:
            return None

        value = dq.popleft()
        if not dq:
            self.delete(key)
        return value

    def rpop(self, key: str) -> Optional[str]:
        """List 오른쪽에서 값을 꺼냅니다. 비어있으면 None."""
        obj = self.get(key)
        if obj is None:
            return None

        dq = obj.value
        if not dq:
            return None

        value = dq.pop()
        if not dq:
            self.delete(key)
        return value

    def lrange(self, key: str, start: int, stop: int) -> List[str]:
        """
        List의 start~stop 범위를 반환합니다.
        음수 인덱스 지원: -1은 마지막 원소
        """
        obj = self.get(key)
        if obj is None:
            return []

        items = list(obj.value)
        n = len(items)
        if n == 0:
            return []

        if start < 0:
            start += n
        if stop < 0:
            stop += n

        if start < 0:
            start = 0
        if stop < 0:
            return []
        if start >= n:
            return []
        if stop >= n:
            stop = n - 1
        if start > stop:
            return []

        return items[start:stop + 1]

    def llen(self, key: str) -> int:
        """List의 길이를 반환합니다."""
        obj = self.get(key)
        if obj is None:
            return 0
        return len(obj.value)

    # ─────────────────────────────────────────
    # Set 전용 메서드
    # ─────────────────────────────────────────

    def sadd(self, key: str, *members: str) -> int:
        raise NotImplementedError

    def srem(self, key: str, *members: str) -> int:
        raise NotImplementedError

    def smembers(self, key: str) -> set:
        raise NotImplementedError

    def sismember(self, key: str, member: str) -> bool:
        raise NotImplementedError

    def scard(self, key: str) -> int:
        raise NotImplementedError

    # ─────────────────────────────────────────
    # Sorted Set 전용 메서드
    # ─────────────────────────────────────────

    def zadd(self, key: str, score: float, member: str) -> int:
        raise NotImplementedError

    def zrem(self, key: str, member: str) -> int:
        raise NotImplementedError

    def zscore(self, key: str, member: str) -> Optional[float]:
        raise NotImplementedError

    def zrange(self, key: str, start: int, stop: int) -> List[str]:
        raise NotImplementedError

    def zrank(self, key: str, member: str) -> Optional[int]:
        raise NotImplementedError

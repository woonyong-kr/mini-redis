"""
인메모리 데이터 스토어 (팀원 B 담당)

모든 키-값 데이터를 메모리에 저장하고 관리합니다.
각 메서드를 구현하세요. 메서드 이름과 파라미터는 변경하지 마세요.
"""

import fnmatch
from collections import deque
from typing import Optional, Any, List, Callable

from store.redis_object import (
    RedisObject,
    TYPE_STRING, TYPE_HASH, TYPE_LIST, TYPE_SET, TYPE_ZSET, TYPE_NONE,
    make_string, make_hash, make_list, make_set, make_zset,
)


class DataStore:
    """
    인메모리 키-값 스토어.

    내부 구조:
      self._data: dict  - 실제 데이터 저장
                          {"key": RedisObject} 형태
                          RedisObject.type으로 Hash/ZSet 등 타입 구분 가능
    """

    def __init__(self):
        # 키 → RedisObject 매핑
        self._data: dict[str, RedisObject] = {}
        self._delete_hooks: list[Callable[[str], None]] = []

    # ─────────────────────────────────────────
    # 범용 메서드
    # ─────────────────────────────────────────

    def register_delete_hook(self, hook: Callable[[str], None]) -> None:
        """키 삭제 시 호출할 훅을 등록합니다."""
        self._delete_hooks.append(hook)

    def get(self, key: str) -> Optional[RedisObject]:
        """
        키에 저장된 RedisObject를 반환합니다.
        키가 없으면 None을 반환합니다.
        """
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
        return key in self._data

    def get_type(self, key: str) -> str:
        """
        키에 저장된 값의 Redis 타입을 반환합니다.
        반환값: "string" | "hash" | "list" | "set" | "zset" | "none"

        RedisObject.type으로 바로 구분하므로 Hash/ZSet 혼동 없음.
        """
        obj = self._data.get(key)
        if obj is None:
            return TYPE_NONE
        return obj.type

    def keys(self, pattern: str = "*") -> List[str]:
        """
        패턴에 매칭되는 키 목록을 반환합니다.
        pattern="*" 이면 전체 키를 반환합니다.

        fnmatch 모듈로 글로브 패턴 지원 (*, ?, [...])
        """
        if pattern == "*":
            return list(self._data.keys())
        return [k for k in self._data if fnmatch.fnmatch(k, pattern)]

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

    def hget(self, key: str, field: str) -> Optional[str]:
        """Hash에서 특정 필드의 값을 반환합니다."""
        raise NotImplementedError

    def hset(self, key: str, field: str, value: str) -> int:
        """
        Hash에 필드를 설정합니다.
        반환: 새로 추가된 필드면 1, 업데이트면 0
        """
        raise NotImplementedError

    def hdel(self, key: str, *fields: str) -> int:
        """Hash에서 필드를 삭제합니다. 반환: 삭제된 수"""
        raise NotImplementedError

    def hgetall(self, key: str) -> dict:
        """Hash의 모든 필드와 값을 반환합니다."""
        raise NotImplementedError

    def hexists(self, key: str, field: str) -> bool:
        """Hash에 필드가 존재하는지 확인합니다."""
        raise NotImplementedError

    # ─────────────────────────────────────────
    # List 전용 메서드
    # ─────────────────────────────────────────

    def lpush(self, key: str, *values: str) -> int:
        """
        List 왼쪽에 값을 추가합니다.
        반환: 추가 후 리스트 길이
        """
        raise NotImplementedError

    def rpush(self, key: str, *values: str) -> int:
        """
        List 오른쪽에 값을 추가합니다.
        반환: 추가 후 리스트 길이
        """
        raise NotImplementedError

    def lpop(self, key: str) -> Optional[str]:
        """List 왼쪽에서 값을 꺼냅니다. 비어있으면 None."""
        raise NotImplementedError

    def rpop(self, key: str) -> Optional[str]:
        """List 오른쪽에서 값을 꺼냅니다. 비어있으면 None."""
        raise NotImplementedError

    def lrange(self, key: str, start: int, stop: int) -> List[str]:
        """
        List의 start~stop 범위를 반환합니다.
        음수 인덱스 지원: -1은 마지막 원소
        """
        raise NotImplementedError

    def llen(self, key: str) -> int:
        """List의 길이를 반환합니다."""
        raise NotImplementedError

    # ─────────────────────────────────────────
    # Set 전용 메서드
    # ─────────────────────────────────────────

    def sadd(self, key: str, *members: str) -> int:
        """Set에 멤버를 추가합니다. 반환: 새로 추가된 수"""
        raise NotImplementedError

    def srem(self, key: str, *members: str) -> int:
        """Set에서 멤버를 삭제합니다. 반환: 삭제된 수"""
        raise NotImplementedError

    def smembers(self, key: str) -> set:
        """Set의 모든 멤버를 반환합니다."""
        raise NotImplementedError

    def sismember(self, key: str, member: str) -> bool:
        """Set에 멤버가 존재하는지 확인합니다."""
        raise NotImplementedError

    def scard(self, key: str) -> int:
        """Set의 멤버 수를 반환합니다."""
        raise NotImplementedError

    # ─────────────────────────────────────────
    # Sorted Set 전용 메서드
    # ─────────────────────────────────────────

    def zadd(self, key: str, score: float, member: str) -> int:
        """
        Sorted Set에 멤버를 추가합니다.
        반환: 새로 추가되면 1, 업데이트면 0
        """
        raise NotImplementedError

    def zrem(self, key: str, member: str) -> int:
        """Sorted Set에서 멤버를 삭제합니다. 반환: 삭제된 수"""
        raise NotImplementedError

    def zscore(self, key: str, member: str) -> Optional[float]:
        """멤버의 score를 반환합니다. 없으면 None."""
        raise NotImplementedError

    def zrange(self, key: str, start: int, stop: int) -> List[str]:
        """
        score 오름차순으로 start~stop 범위의 멤버를 반환합니다.
        """
        raise NotImplementedError

    def zrank(self, key: str, member: str) -> Optional[int]:
        """score 오름차순 기준 멤버의 순위(0부터)를 반환합니다."""
        raise NotImplementedError

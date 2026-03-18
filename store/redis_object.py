"""Shared object wrappers used by the in-memory store.

Every key stores one `RedisObject` that records the logical Redis type, the
chosen internal encoding, and the concrete Python value that backs it.
"""

from __future__ import annotations

from typing import Any, Union
from store.skiplist import ZSet


# ─────────────────────────────────────────
# 타입 상수 (Redis TYPE 명령어 반환값과 동일)
# ─────────────────────────────────────────
TYPE_STRING = "string"
TYPE_HASH   = "hash"
TYPE_LIST   = "list"
TYPE_SET    = "set"
TYPE_ZSET   = "zset"
TYPE_NONE   = "none"   # 키가 존재하지 않을 때

# ─────────────────────────────────────────
# 인코딩 상수 (내부 저장 방식)
# ─────────────────────────────────────────
ENC_RAW       = "raw"       # 일반 문자열
ENC_INT       = "int"       # 정수로 변환 가능한 문자열 (최적화용)
ENC_DICT      = "dict"      # Python dict
ENC_DEQUE     = "deque"     # collections.deque (List)
ENC_HASHTABLE = "hashtable" # Python set (Set)
ENC_SKIPLIST  = "skiplist"  # ZSet 전용

RESP_ENCODING = "utf-8"
RESP_ERRORS = "surrogateescape"


class RedisObject:
    """Wraps one stored value with its logical type and encoding."""

    __slots__ = ("type", "encoding", "value", "refcount")

    def __init__(self, type: str, encoding: str, value: Any):
        self.type = type
        self.encoding = encoding
        self.value = value
        self.refcount = 1

    def __repr__(self) -> str:
        return (
            f"RedisObject(type={self.type!r}, "
            f"encoding={self.encoding!r}, "
            f"value={self.value!r})"
        )


def to_bytes(value: Union[str, bytes]) -> bytes:
    """Uses the same codec policy as the RESP parser/encoder path."""
    if isinstance(value, bytes):
        return value
    return value.encode(RESP_ENCODING, errors=RESP_ERRORS)


def make_string(value: Union[str, bytes]) -> RedisObject:
    """Builds a string object and records whether it can be treated as an int."""
    if value is None:
        raise ValueError("value cannot be None")

    raw_value = to_bytes(value)
    if _is_integer_string(raw_value):
        encoding = ENC_INT
    else:
        encoding = ENC_RAW
    return RedisObject(TYPE_STRING, encoding, raw_value)

def make_hash(value: Any = None) -> RedisObject:
    """Builds a hash object from either a custom hash table or a plain mapping."""
    if value is None:
        return RedisObject(TYPE_HASH, ENC_DICT, {})
    if isinstance(value, dict):
        return RedisObject(TYPE_HASH, ENC_DICT, value)
    return RedisObject(TYPE_HASH, ENC_HASHTABLE, value)


def make_list(value=None) -> RedisObject:
    """Builds a list object backed by `collections.deque`."""
    from collections import deque
    return RedisObject(TYPE_LIST, ENC_DEQUE, value if value is not None else deque())


def make_set(value: set = None) -> RedisObject:
    """Builds a set object backed by Python's hash set."""
    return RedisObject(TYPE_SET, ENC_HASHTABLE, value if value is not None else set())


def make_zset(value: Any = None) -> RedisObject:
    """Builds a sorted set object backed by the local `ZSet` wrapper."""
    if value is None:
        zset = ZSet()
    elif isinstance(value, ZSet):
        zset = value
    elif isinstance(value, dict):
        zset = ZSet.from_items(value.items())
    else:
        zset = ZSet.from_items(value)
    return RedisObject(TYPE_ZSET, ENC_SKIPLIST, zset)


def _is_integer_string(s: Union[str, bytes]) -> bool:
    """Returns True when a bytes/string payload can be parsed as an integer."""
    try:
        int(s)
        return True
    except (ValueError, TypeError):
        return False

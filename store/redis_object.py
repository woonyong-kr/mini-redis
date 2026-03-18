"""
RedisObject - Redis의 핵심 추상화 자료형

실제 Redis C 코드의 robj(redisObject) 구조체를 Python으로 구현합니다.

Redis의 모든 값은 타입에 상관없이 RedisObject 하나로 표현됩니다.
  - type    : 논리적 타입 (string, hash, list, set, zset)
  - encoding: 물리적 인코딩 방식 (실제 데이터가 어떤 구조로 저장되는지)
  - value   : 실제 데이터
  - refcount: 참조 카운트 (현재는 구조 반영용, 항상 1)

예시:
  SET foo bar  →  RedisObject(type="string", encoding="raw",  value="bar")
  HSET h f v   →  RedisObject(type="hash",   encoding="dict", value={"f": "v"})
"""

from typing import Any


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
ENC_DICT      = "dict"      # Python dict (Hash, ZSet 임시 구현)
ENC_DEQUE     = "deque"     # collections.deque (List)
ENC_HASHTABLE = "hashtable" # Python set (Set)
ENC_SKIPLIST  = "skiplist"  # ZSet 전용 (현재는 dict로 구현, 추후 교체)


class RedisObject:
    """
    Redis의 모든 값을 표현하는 범용 래퍼 클래스.

    실제 Redis의 redisObject 구조체:
      typedef struct redisObject {
          unsigned type:4;
          unsigned encoding:4;
          void *ptr;          ← 여기서는 value
          int refcount;
      } robj;
    """

    __slots__ = ("type", "encoding", "value", "refcount")

    def __init__(self, type: str, encoding: str, value: Any):
        self.type     = type      # TYPE_STRING, TYPE_HASH, ...
        self.encoding = encoding  # ENC_RAW, ENC_INT, ENC_DICT, ...
        self.value    = value     # 실제 데이터
        self.refcount = 1         # 참조 카운트 (현재는 항상 1)

    def __repr__(self) -> str:
        return (
            f"RedisObject(type={self.type!r}, "
            f"encoding={self.encoding!r}, "
            f"value={self.value!r})"
        )


# ─────────────────────────────────────────
# 팩토리 함수 - 타입별 RedisObject 생성
# ─────────────────────────────────────────

def make_string(value: str) -> RedisObject:

    """
    String 타입 RedisObject 생성.
    값이 정수로 변환 가능하면 ENC_INT, 아니면 ENC_RAW 인코딩 사용.
    """

    # 1. 입력 검증
    if value is None:
        raise ValueError("value cannot be None")

    # 2. 인코딩 결정 (핵심 로직)
    if _is_integer_string(value):
        encoding = ENC_INT
    else:
        encoding = ENC_RAW

    # 3. RedisObject 생성
    obj = RedisObject(TYPE_STRING, encoding, value)

    return obj

def make_hash(value: dict = None) -> RedisObject:
    """
    Hash 타입 RedisObject 생성.
    value는 Python dict를 사용합니다. (추후 직접 구현한 해시로 교체 예정)

    예: make_hash({"field": "value"})
    """
    return RedisObject(TYPE_HASH, ENC_DICT, value if value is not None else {})


def make_list(value=None) -> RedisObject:
    """
    List 타입 RedisObject 생성.
    value는 collections.deque를 사용합니다.
    """
    from collections import deque
    return RedisObject(TYPE_LIST, ENC_DEQUE, value if value is not None else deque())


def make_set(value: set = None) -> RedisObject:
    """
    Set 타입 RedisObject 생성.
    value는 Python set을 사용합니다.
    """
    return RedisObject(TYPE_SET, ENC_HASHTABLE, value if value is not None else set())


def make_zset(value: dict = None) -> RedisObject:
    """
    Sorted Set 타입 RedisObject 생성.
    value는 {"member": score} 형태의 Python dict를 사용합니다.
    (추후 직접 구현한 스킵리스트로 교체 예정)
    """
    return RedisObject(TYPE_ZSET, ENC_SKIPLIST, value if value is not None else {})


# ─────────────────────────────────────────
# 내부 헬퍼
# ─────────────────────────────────────────

def _is_integer_string(s: str) -> bool:
    """문자열이 정수로 변환 가능한지 확인합니다."""
    try:
        int(s)
        return True
    except (ValueError, TypeError):
        return False

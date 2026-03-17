"""
List 명령어 핸들러 (팀원 D 담당)
"""

from typing import List
from store.datastore import DataStore
from store.expiry import ExpiryManager
from protocol.encoder import (
    encode_simple_string, encode_bulk_string,
    encode_error, encode_integer, encode_array
)

WRONGTYPE_ERROR = "WRONGTYPE Operation against a key holding the wrong kind of value"


def cmd_lpush(store: DataStore, expiry: ExpiryManager, args: List[str]) -> bytes:
    """
    LPUSH key value [value ...]
    왼쪽에 추가. 여러 값은 왼쪽부터 순서대로 추가됩니다.
    반환: 추가 후 리스트 길이 (integer)
    """
    raise NotImplementedError


def cmd_rpush(store: DataStore, expiry: ExpiryManager, args: List[str]) -> bytes:
    """
    RPUSH key value [value ...]
    오른쪽에 추가.
    반환: 추가 후 리스트 길이 (integer)
    """
    raise NotImplementedError


def cmd_lpop(store: DataStore, expiry: ExpiryManager, args: List[str]) -> bytes:
    """
    LPOP key
    왼쪽에서 꺼냅니다.
    반환: 꺼낸 값 (bulk string) 또는 nil
    """
    raise NotImplementedError


def cmd_rpop(store: DataStore, expiry: ExpiryManager, args: List[str]) -> bytes:
    """
    RPOP key
    오른쪽에서 꺼냅니다.
    반환: 꺼낸 값 (bulk string) 또는 nil
    """
    raise NotImplementedError


def cmd_lrange(store: DataStore, expiry: ExpiryManager, args: List[str]) -> bytes:
    """
    LRANGE key start stop
    start부터 stop까지의 원소를 반환합니다.
    음수 인덱스 지원: -1은 마지막, -2는 끝에서 두 번째
    반환: 배열 (array)
    """
    raise NotImplementedError


def cmd_llen(store: DataStore, expiry: ExpiryManager, args: List[str]) -> bytes:
    """
    LLEN key
    반환: 리스트 길이 (integer). 키 없으면 0.
    """
    raise NotImplementedError


def cmd_lindex(store: DataStore, expiry: ExpiryManager, args: List[str]) -> bytes:
    """
    LINDEX key index
    특정 인덱스의 원소를 반환합니다.
    반환: 값 (bulk string) 또는 nil (범위 초과)
    """
    raise NotImplementedError


def cmd_lset(store: DataStore, expiry: ExpiryManager, args: List[str]) -> bytes:
    """
    LSET key index value
    특정 인덱스의 원소를 변경합니다.
    반환: +OK 또는 오류 (인덱스 범위 초과)
    """
    raise NotImplementedError

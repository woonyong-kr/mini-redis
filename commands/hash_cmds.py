"""
Hash 명령어 핸들러 (팀원 D 담당)
"""

from typing import List
from store.datastore import DataStore
from store.expiry import ExpiryManager
from protocol.encoder import (
    encode_simple_string, encode_bulk_string,
    encode_error, encode_integer, encode_array
)

WRONGTYPE_ERROR = "WRONGTYPE Operation against a key holding the wrong kind of value"


def cmd_hset(store: DataStore, expiry: ExpiryManager, args: List[str]) -> bytes:
    """
    HSET key field value [field value ...]
    반환: 새로 추가된 필드 수 (integer)
    """
    raise NotImplementedError


def cmd_hget(store: DataStore, expiry: ExpiryManager, args: List[str]) -> bytes:
    """
    HGET key field
    반환: 필드 값 (bulk string) 또는 nil
    """
    raise NotImplementedError


def cmd_hmset(store: DataStore, expiry: ExpiryManager, args: List[str]) -> bytes:
    """
    HMSET key field value [field value ...]
    반환: +OK
    """
    raise NotImplementedError


def cmd_hmget(store: DataStore, expiry: ExpiryManager, args: List[str]) -> bytes:
    """
    HMGET key field [field ...]
    반환: 값 배열 (없는 필드는 nil)
    """
    raise NotImplementedError


def cmd_hgetall(store: DataStore, expiry: ExpiryManager, args: List[str]) -> bytes:
    """
    HGETALL key
    반환: [field1, value1, field2, value2, ...] 형태의 배열
    """
    raise NotImplementedError


def cmd_hdel(store: DataStore, expiry: ExpiryManager, args: List[str]) -> bytes:
    """
    HDEL key field [field ...]
    반환: 삭제된 필드 수 (integer)
    """
    raise NotImplementedError


def cmd_hexists(store: DataStore, expiry: ExpiryManager, args: List[str]) -> bytes:
    """
    HEXISTS key field
    반환: 1(존재) 또는 0(없음) (integer)
    """
    raise NotImplementedError


def cmd_hkeys(store: DataStore, expiry: ExpiryManager, args: List[str]) -> bytes:
    """
    HKEYS key
    반환: 필드명 배열
    """
    raise NotImplementedError


def cmd_hvals(store: DataStore, expiry: ExpiryManager, args: List[str]) -> bytes:
    """
    HVALS key
    반환: 값 배열
    """
    raise NotImplementedError


def cmd_hlen(store: DataStore, expiry: ExpiryManager, args: List[str]) -> bytes:
    """
    HLEN key
    반환: 필드 수 (integer)
    """
    raise NotImplementedError

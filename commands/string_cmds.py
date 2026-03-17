"""
String 명령어 핸들러 (팀원 C 담당)

모든 함수는 동일한 시그니처를 가집니다:
  (store, expiry, args) → bytes

args: 명령어 뒤의 인자 리스트 (명령어 이름 제외)
예: "SET foo bar" → args = ["foo", "bar"]
"""

from typing import List
from store.datastore import DataStore
from store.expiry import ExpiryManager
from protocol.encoder import (
    encode_simple_string, encode_bulk_string,
    encode_error, encode_integer, encode_array
)


def cmd_get(store: DataStore, expiry: ExpiryManager, args: List[str]) -> bytes:
    """
    GET key
    키에 저장된 값을 반환합니다. 없으면 nil($-1\r\n)을 반환합니다.

    오류 케이스:
      - 인자가 1개 아닐 때: ERR wrong number of arguments
      - 값이 string 타입이 아닐 때: WRONGTYPE error
    """
    raise NotImplementedError


def cmd_set(store: DataStore, expiry: ExpiryManager, args: List[str]) -> bytes:
    """
    SET key value [EX seconds] [PX milliseconds]
    값을 저장합니다. 성공하면 +OK를 반환합니다.

    옵션 처리:
      EX seconds  → 초 단위 만료
      PX ms       → 밀리초 단위 만료 (선택 구현)
    """
    raise NotImplementedError


def cmd_mget(store: DataStore, expiry: ExpiryManager, args: List[str]) -> bytes:
    """
    MGET key [key ...]
    여러 키의 값을 배열로 반환합니다. 없는 키는 nil로 반환합니다.
    """
    raise NotImplementedError


def cmd_mset(store: DataStore, expiry: ExpiryManager, args: List[str]) -> bytes:
    """
    MSET key value [key value ...]
    여러 키에 값을 한 번에 저장합니다.
    인자가 홀수개면 오류를 반환합니다.
    """
    raise NotImplementedError


def cmd_incr(store: DataStore, expiry: ExpiryManager, args: List[str]) -> bytes:
    """
    INCR key
    정수 값을 1 증가시킵니다. 키가 없으면 0에서 시작합니다.
    오류: 값이 정수가 아닐 때 "ERR value is not an integer"
    """
    raise NotImplementedError


def cmd_decr(store: DataStore, expiry: ExpiryManager, args: List[str]) -> bytes:
    """
    DECR key
    정수 값을 1 감소시킵니다. 키가 없으면 0에서 시작합니다.
    """
    raise NotImplementedError


def cmd_incrby(store: DataStore, expiry: ExpiryManager, args: List[str]) -> bytes:
    """
    INCRBY key increment
    정수 값을 increment만큼 증가시킵니다.
    """
    raise NotImplementedError


def cmd_append(store: DataStore, expiry: ExpiryManager, args: List[str]) -> bytes:
    """
    APPEND key value
    문자열 뒤에 value를 이어붙입니다.
    반환: 이어붙인 후 문자열의 길이 (integer)
    """
    raise NotImplementedError


def cmd_strlen(store: DataStore, expiry: ExpiryManager, args: List[str]) -> bytes:
    """
    STRLEN key
    문자열의 길이를 반환합니다. 키가 없으면 0을 반환합니다.
    """
    raise NotImplementedError

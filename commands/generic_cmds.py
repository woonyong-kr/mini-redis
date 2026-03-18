"""
Generic 명령어 핸들러 (팀원 C 담당)

키 타입에 상관없이 모든 키에 적용되는 명령어들입니다.
"""

from __future__ import annotations

from typing import List, Any
from store.datastore import DataStore
from store.expiry import ExpiryManager
from protocol.encoder import SimpleString, RespError


def _wrong_number(command: str) -> RespError:
    return RespError(f"ERR wrong number of arguments for '{command}' command")


def cmd_ping(store: DataStore, expiry: ExpiryManager, args: List[str]) -> Any:
    """
    PING [message]
    message 없으면 +PONG, 있으면 bulk string으로 message 반환.
    """
    if len(args) > 1:
        return _wrong_number("ping")
    if not args:
        return SimpleString("PONG")
    return args[0]


def cmd_del(store: DataStore, expiry: ExpiryManager, args: List[str]) -> Any:
    """
    DEL key [key ...]
    키를 삭제합니다. 반환: 실제로 삭제된 키의 수 (integer)
    """
    if not args:
        return _wrong_number("del")

    deleted = 0
    for key in args:
        if not store.exists(key):
            continue
        deleted += store.delete(key)
    return deleted


def cmd_exists(store: DataStore, expiry: ExpiryManager, args: List[str]) -> Any:
    """
    EXISTS key [key ...]
    키의 존재 여부를 반환합니다.
    반환: 존재하는 키의 수 (integer, 중복 키 포함)
    """
    if not args:
        return _wrong_number("exists")

    count = 0
    for key in args:
        if store.exists(key):
            count += 1
    return count


def cmd_expire(store: DataStore, expiry: ExpiryManager, args: List[str]) -> Any:
    """
    EXPIRE key seconds
    키의 만료 시간을 설정합니다.
    반환: 1(성공) 또는 0(키 없음) (integer)
    """
    if len(args) != 2:
        return _wrong_number("expire")

    key, seconds_arg = args
    try:
        seconds = int(seconds_arg)
    except ValueError:
        return RespError("ERR value is not an integer or out of range")

    if not store.exists(key):
        return 0

    expiry.set_expiry(key, seconds)
    if expiry.is_expired(key):
        store.delete(key)
    return 1


def cmd_ttl(store: DataStore, expiry: ExpiryManager, args: List[str]) -> Any:
    """
    TTL key
    남은 만료 시간(초)을 반환합니다.
    반환: 남은 초 | -1(만료 없음) | -2(키 없음) (integer)
    """
    if len(args) != 1:
        return _wrong_number("ttl")

    ttl = expiry.get_ttl(args[0])
    if ttl > 0:
        return int(ttl)
    return int(ttl)


def cmd_persist(store: DataStore, expiry: ExpiryManager, args: List[str]) -> Any:
    """
    PERSIST key
    키의 만료 설정을 제거합니다 (영구 보존).
    반환: 1(제거 성공) 또는 0(만료 없거나 키 없음) (integer)
    """
    if len(args) != 1:
        return _wrong_number("persist")

    key = args[0]
    ttl = expiry.get_ttl(key)
    if ttl in (-1, -2):
        return 0

    expiry.remove_expiry(key)
    return 1


def cmd_type(store: DataStore, expiry: ExpiryManager, args: List[str]) -> Any:
    """
    TYPE key
    키의 타입을 반환합니다.
    반환: "string" | "hash" | "list" | "set" | "zset" | "none" (simple string)
    """
    if len(args) != 1:
        return _wrong_number("type")
    return SimpleString(store.get_type(args[0]))


def cmd_keys(store: DataStore, expiry: ExpiryManager, args: List[str]) -> Any:
    """
    KEYS pattern
    패턴에 맞는 키 목록을 반환합니다.
    예: KEYS * → 전체 키, KEYS foo* → foo로 시작하는 키
    반환: 배열 (array)
    """
    if len(args) != 1:
        return _wrong_number("keys")
    return store.keys(args[0])


def cmd_flushall(store: DataStore, expiry: ExpiryManager, args: List[str]) -> Any:
    """
    FLUSHALL
    모든 데이터를 삭제합니다.
    반환: +OK
    """
    if args:
        return _wrong_number("flushall")
    store.flush()
    return SimpleString("OK")

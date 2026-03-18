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
    message 없으면 SimpleString("PONG"), 있으면 message를 bulk string으로 반환.
    """
    if len(args) > 1:
        return _wrong_number("ping")
    if len(args) == 0:
        return SimpleString("PONG")
    return args[0]


def cmd_del(store: DataStore, expiry: ExpiryManager, args: List[str]) -> Any:
    if not args:
        return _wrong_number("del")

    deleted = 0
    for key in args:
        if not store.exists(key):
            continue
        deleted += store.delete(key)
    return deleted


def cmd_exists(store: DataStore, expiry: ExpiryManager, args: List[str]) -> Any:
    if not args:
        return _wrong_number("exists")

    count = 0
    for key in args:
        if store.exists(key):
            count += 1
    return count


def cmd_expire(store: DataStore, expiry: ExpiryManager, args: List[str]) -> Any:
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
    if len(args) != 1:
        return _wrong_number("ttl")

    return int(expiry.get_ttl(args[0]))


def cmd_persist(store: DataStore, expiry: ExpiryManager, args: List[str]) -> Any:
    if len(args) != 1:
        return _wrong_number("persist")

    key = args[0]
    ttl = expiry.get_ttl(key)
    if ttl in (-1, -2):
        return 0

    expiry.remove_expiry(key)
    return 1


def cmd_type(store: DataStore, expiry: ExpiryManager, args: List[str]) -> Any:
    if len(args) != 1:
        return _wrong_number("type")
    return SimpleString(store.get_type(args[0]))


def cmd_keys(store: DataStore, expiry: ExpiryManager, args: List[str]) -> Any:
    if len(args) != 1:
        return _wrong_number("keys")
    return store.keys(args[0])


def cmd_flushall(store: DataStore, expiry: ExpiryManager, args: List[str]) -> Any:
    if args:
        return _wrong_number("flushall")
    store.flush()
    return SimpleString("OK")

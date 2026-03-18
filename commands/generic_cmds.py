"""Handlers shared by every Redis data type.

These commands either inspect key metadata or control lifecycle state such as
TTL, deletion, and persistence-friendly absolute expiry.
"""

from __future__ import annotations

import time
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


def cmd_pexpireat(store: DataStore, expiry: ExpiryManager, args: List[str]) -> Any:
    if len(args) != 2:
        return _wrong_number("pexpireat")

    key, timestamp_ms_arg = args
    try:
        timestamp_ms = int(timestamp_ms_arg)
    except ValueError:
        return RespError("ERR value is not an integer or out of range")

    if not store.exists(key):
        return 0

    expiry_at = timestamp_ms / 1000.0
    if expiry_at <= time.time():
        store.delete(key, reason="expiry")
        return 1

    expiry.set_expiry_at(key, expiry_at)
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

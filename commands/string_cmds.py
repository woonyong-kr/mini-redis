"""String command handlers for the mini-redis core profile.

The file keeps one narrow flow for every command:
validate arguments, verify type, mutate the store, then adjust TTL state.
`MSET` is the only multi-key write here, so it also carries rollback logic.
"""

from __future__ import annotations

from typing import Any, List

from protocol.encoder import RespError, SimpleString
from store.datastore import DataStore
from store.expiry import ExpiryManager
from store.redis_object import TYPE_STRING, make_string, to_bytes


WRONGTYPE_ERROR = "WRONGTYPE Operation against a key holding the wrong kind of value"
INTEGER_ERROR = "ERR value is not an integer or out of range"


def _wrong_number(command: str) -> RespError:
    return RespError(f"ERR wrong number of arguments for '{command}' command")


def _string_object(store: DataStore, key: str):
    obj = store.get(key)
    if obj is None:
        return None
    if obj.type != TYPE_STRING:
        return RespError(WRONGTYPE_ERROR)
    return obj


def _require_integer(value: bytes) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def cmd_get(store: DataStore, expiry: ExpiryManager, args: List[str]) -> Any:
    if len(args) != 1:
        return _wrong_number("get")

    obj = _string_object(store, args[0])
    if obj is None:
        return None
    if isinstance(obj, RespError):
        return obj
    return obj.value


def cmd_set(store: DataStore, expiry: ExpiryManager, args: List[str]) -> Any:
    if len(args) < 2:
        return _wrong_number("set")

    key = args[0]
    value = args[1]
    expiry_seconds = None
    index = 2

    while index < len(args):
        option = args[index].upper()

        if option == "EX" and index + 1 < len(args):
            try:
                seconds = int(args[index + 1])
            except ValueError:
                return RespError(INTEGER_ERROR)
            if seconds <= 0:
                return RespError("ERR invalid expire time in 'set' command")
            expiry_seconds = float(seconds)
            index += 2
            continue

        if option == "PX" and index + 1 < len(args):
            try:
                milliseconds = int(args[index + 1])
            except ValueError:
                return RespError(INTEGER_ERROR)
            if milliseconds <= 0:
                return RespError("ERR invalid expire time in 'set' command")
            expiry_seconds = milliseconds / 1000.0
            index += 2
            continue

        return RespError("ERR syntax error")

    store.set(key, make_string(value))
    expiry.remove_expiry(key)
    if expiry_seconds is not None:
        expiry.set_expiry(key, expiry_seconds)
    return SimpleString("OK")


def cmd_mget(store: DataStore, expiry: ExpiryManager, args: List[str]) -> Any:
    if not args:
        return _wrong_number("mget")

    values = []
    for key in args:
        obj = _string_object(store, key)
        if isinstance(obj, RespError):
            return obj
        values.append(None if obj is None else obj.value)
    return values


def cmd_mset(store: DataStore, expiry: ExpiryManager, args: List[str]) -> Any:
    if not args or len(args) % 2 != 0:
        return _wrong_number("mset")

    snapshots = {}
    expiry_snapshots = {}
    for index in range(0, len(args), 2):
        key = args[index]
        if key not in snapshots:
            snapshots[key] = store._snapshot_key(key)
            expiry_snapshots[key] = expiry.get_expiry_at(key)

    try:
        for index in range(0, len(args), 2):
            key = args[index]
            value = args[index + 1]
            store.set(key, make_string(value))
            expiry.remove_expiry(key)
    except Exception:
        for key, snapshot in snapshots.items():
            store._restore_key_snapshot(key, snapshot)
            expiry_at = expiry_snapshots[key]
            if expiry_at is None:
                expiry.remove_expiry(key)
            else:
                expiry.set_expiry_at(key, expiry_at)
        raise

    return SimpleString("OK")


def cmd_incr(store: DataStore, expiry: ExpiryManager, args: List[str]) -> Any:
    if len(args) != 1:
        return _wrong_number("incr")
    return cmd_incrby(store, expiry, [args[0], "1"])


def cmd_decr(store: DataStore, expiry: ExpiryManager, args: List[str]) -> Any:
    if len(args) != 1:
        return _wrong_number("decr")
    return cmd_incrby(store, expiry, [args[0], "-1"])


def cmd_incrby(store: DataStore, expiry: ExpiryManager, args: List[str]) -> Any:
    if len(args) != 2:
        return _wrong_number("incrby")

    key, increment_raw = args
    try:
        increment = int(increment_raw)
    except ValueError:
        return RespError(INTEGER_ERROR)

    obj = _string_object(store, key)
    if isinstance(obj, RespError):
        return obj

    current = 0
    if obj is not None:
        current = _require_integer(obj.value)
        if current is None:
            return RespError(INTEGER_ERROR)

    updated = current + increment
    store.set(key, make_string(str(updated)))
    return updated


def cmd_append(store: DataStore, expiry: ExpiryManager, args: List[str]) -> Any:
    if len(args) != 2:
        return _wrong_number("append")

    key, value = args
    obj = _string_object(store, key)
    if isinstance(obj, RespError):
        return obj

    append_value = to_bytes(value)
    if obj is None:
        store.set(key, make_string(append_value))
        return len(append_value)

    updated = obj.value + append_value
    store.set(key, make_string(updated))
    return len(updated)


def cmd_strlen(store: DataStore, expiry: ExpiryManager, args: List[str]) -> Any:
    if len(args) != 1:
        return _wrong_number("strlen")

    obj = _string_object(store, args[0])
    if isinstance(obj, RespError):
        return obj
    if obj is None:
        return 0
    return len(obj.value)

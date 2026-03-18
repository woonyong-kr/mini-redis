"""Hash command handlers.

The public profile keeps the hash surface small: field writes, reads, deletes,
existence checks, and whole-hash reads used by session-style workloads.
"""

from __future__ import annotations

from typing import List, Any
from store.datastore import DataStore, TYPE_HASH, TYPE_NONE
from store.expiry import ExpiryManager
from protocol.encoder import SimpleString, RespError
from store.hash_table import Hash

WRONGTYPE_ERROR = "WRONGTYPE Operation against a key holding the wrong kind of value"


def _wrong_number(command: str) -> RespError:
    return RespError(f"ERR wrong number of arguments for '{command}' command")


def _type_check(store: DataStore, key: str) -> RespError | None:
    key_type = store.get_type(key)
    if key_type in (TYPE_NONE, TYPE_HASH):
        return None
    return RespError(WRONGTYPE_ERROR)


def _get_hash_object(store: DataStore, key: str) -> Hash | None:
    return store._get_hash_table(key)


def cmd_hset(store: DataStore, expiry: ExpiryManager, args: List[str]) -> Any:
    """
    HSET key field value [field value ...]
    반환: 새로 추가된 필드 수 (integer)
    """
    if len(args) < 3 or len(args) % 2 == 0:
        return _wrong_number("hset")

    key = args[0]
    type_error = _type_check(store, key)
    if type_error is not None:
        return type_error

    snapshot = store._snapshot_key(key)
    added = 0
    try:
        for index in range(1, len(args), 2):
            field = args[index]
            value = args[index + 1]
            added += store.hset(key, field, value)
    except Exception:
        store._restore_key_snapshot(key, snapshot)
        raise
    return added


def cmd_hget(store: DataStore, expiry: ExpiryManager, args: List[str]) -> Any:
    """
    HGET key field
    반환: 필드 값 (bulk string) 또는 nil
    """
    if len(args) != 2:
        return _wrong_number("hget")

    key, field = args
    type_error = _type_check(store, key)
    if type_error is not None:
        return type_error
    return store.hget(key, field)


def cmd_hmset(store: DataStore, expiry: ExpiryManager, args: List[str]) -> Any:
    """
    HMSET key field value [field value ...]
    반환: +OK
    """
    if len(args) < 3 or len(args) % 2 == 0:
        return _wrong_number("hmset")

    key = args[0]
    type_error = _type_check(store, key)
    if type_error is not None:
        return type_error

    snapshot = store._snapshot_key(key)
    try:
        for index in range(1, len(args), 2):
            field = args[index]
            value = args[index + 1]
            store.hset(key, field, value)
    except Exception:
        store._restore_key_snapshot(key, snapshot)
        raise
    return SimpleString("OK")


def cmd_hmget(store: DataStore, expiry: ExpiryManager, args: List[str]) -> Any:
    """
    HMGET key field [field ...]
    반환: 값 배열 (없는 필드는 nil)
    """
    if len(args) < 2:
        return _wrong_number("hmget")

    key = args[0]
    fields = args[1:]
    type_error = _type_check(store, key)
    if type_error is not None:
        return type_error

    if store.get_type(key) == TYPE_NONE:
        return [None for _ in fields]

    return [store.hget(key, field) for field in fields]


def cmd_hgetall(store: DataStore, expiry: ExpiryManager, args: List[str]) -> Any:
    """
    HGETALL key
    반환: [field1, value1, field2, value2, ...] 형태의 배열
    """
    if len(args) != 1:
        return _wrong_number("hgetall")

    key = args[0]
    type_error = _type_check(store, key)
    if type_error is not None:
        return type_error

    hash_value = _get_hash_object(store, key)
    if hash_value is None:
        return []

    result: List[str] = []
    for field, value in hash_value.items():
        result.append(field)
        result.append(value)
    return result


def cmd_hdel(store: DataStore, expiry: ExpiryManager, args: List[str]) -> Any:
    """
    HDEL key field [field ...]
    반환: 삭제된 필드 수 (integer)
    """
    if len(args) < 2:
        return _wrong_number("hdel")

    key = args[0]
    fields = args[1:]
    type_error = _type_check(store, key)
    if type_error is not None:
        return type_error
    return store.hdel(key, *fields)


def cmd_hexists(store: DataStore, expiry: ExpiryManager, args: List[str]) -> Any:
    """
    HEXISTS key field
    반환: 1(존재) 또는 0(없음) (integer)
    """
    if len(args) != 2:
        return _wrong_number("hexists")

    key, field = args
    type_error = _type_check(store, key)
    if type_error is not None:
        return type_error
    return 1 if store.hexists(key, field) else 0


def cmd_hkeys(store: DataStore, expiry: ExpiryManager, args: List[str]) -> Any:
    """
    HKEYS key
    반환: 필드명 배열
    """
    if len(args) != 1:
        return _wrong_number("hkeys")

    key = args[0]
    type_error = _type_check(store, key)
    if type_error is not None:
        return type_error

    hash_value = _get_hash_object(store, key)
    if hash_value is None:
        return []
    return [field for field, _ in hash_value.items()]


def cmd_hvals(store: DataStore, expiry: ExpiryManager, args: List[str]) -> Any:
    """
    HVALS key
    반환: 값 배열
    """
    if len(args) != 1:
        return _wrong_number("hvals")

    key = args[0]
    type_error = _type_check(store, key)
    if type_error is not None:
        return type_error

    hash_value = _get_hash_object(store, key)
    if hash_value is None:
        return []
    return [value for _, value in hash_value.items()]


def cmd_hlen(store: DataStore, expiry: ExpiryManager, args: List[str]) -> Any:
    """
    HLEN key
    반환: 필드 수 (integer)
    """
    if len(args) != 1:
        return _wrong_number("hlen")

    key = args[0]
    type_error = _type_check(store, key)
    if type_error is not None:
        return type_error

    hash_value = _get_hash_object(store, key)
    if hash_value is None:
        return 0
    return len(hash_value)

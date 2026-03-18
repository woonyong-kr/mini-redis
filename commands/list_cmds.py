"""List command handlers.

The list path stays focused on queue-style operations: push, pop, ranged read,
and a couple of indexed helpers used by tests and admin tooling.
"""

from typing import List, Any
from store.datastore import DataStore
from store.expiry import ExpiryManager
from protocol.encoder import SimpleString, RespError

WRONGTYPE_ERROR = "WRONGTYPE Operation against a key holding the wrong kind of value"


def _wrong_number(command: str) -> RespError:
    return RespError(f"ERR wrong number of arguments for '{command}' command")


def cmd_lpush(store: DataStore, expiry: ExpiryManager, args: List[str]) -> Any:
    """
    LPUSH key value [value ...]
    왼쪽에 추가. 여러 값은 왼쪽부터 순서대로 추가됩니다.
    반환: 추가 후 리스트 길이 (integer)
    """
    if len(args) < 2:
        return RespError("ERR wrong number of arguments for 'LPUSH' command")

    key = args[0]
    values = args[1:]

    if store.exists(key) and store.get_type(key) != "list":
        return RespError(WRONGTYPE_ERROR)

    return store.lpush(key, *values)


def cmd_rpush(store: DataStore, expiry: ExpiryManager, args: List[str]) -> Any:
    """
    RPUSH key value [value ...]
    오른쪽에 추가.
    반환: 추가 후 리스트 길이 (integer)
    """
    if len(args) < 2:
        return RespError("ERR wrong number of arguments for 'RPUSH' command")

    key = args[0]
    values = args[1:]

    if store.exists(key) and store.get_type(key) != "list":
        return RespError(WRONGTYPE_ERROR)

    return store.rpush(key, *values)


def cmd_lpop(store: DataStore, expiry: ExpiryManager, args: List[str]) -> Any:
    """
    LPOP key
    왼쪽에서 꺼냅니다.
    반환: 꺼낸 값 (bulk string) 또는 nil
    """
    if len(args) != 1:
        return RespError("ERR wrong number of arguments for 'LPOP' command")

    key = args[0]

    if store.exists(key) and store.get_type(key) != "list":
        return RespError(WRONGTYPE_ERROR)

    return store.lpop(key)


def cmd_rpop(store: DataStore, expiry: ExpiryManager, args: List[str]) -> Any:
    """
    RPOP key
    오른쪽에서 꺼냅니다.
    반환: 꺼낸 값 (bulk string) 또는 nil
    """
    if len(args) != 1:
        return RespError("ERR wrong number of arguments for 'RPOP' command")

    key = args[0]

    if store.exists(key) and store.get_type(key) != "list":
        return RespError(WRONGTYPE_ERROR)

    return store.rpop(key)


def cmd_lrange(store: DataStore, expiry: ExpiryManager, args: List[str]) -> Any:
    """
    LRANGE key start stop
    start부터 stop까지의 원소를 반환합니다.
    음수 인덱스 지원: -1은 마지막, -2는 끝에서 두 번째
    반환: 배열 (array)
    """
    if len(args) != 3:
        return RespError("ERR wrong number of arguments for 'LRANGE' command")

    key = args[0]

    if store.exists(key) and store.get_type(key) != "list":
        return RespError(WRONGTYPE_ERROR)

    try:
        start = int(args[1])
        stop = int(args[2])
    except ValueError:
        return RespError("ERR value is not an integer or out of range")

    return store.lrange(key, start, stop)


def cmd_llen(store: DataStore, expiry: ExpiryManager, args: List[str]) -> Any:
    """
    LLEN key
    반환: 리스트 길이 (integer). 키 없으면 0.
    """
    if len(args) != 1:
        return RespError("ERR wrong number of arguments for 'LLEN' command")

    key = args[0]

    if store.exists(key) and store.get_type(key) != "list":
        return RespError(WRONGTYPE_ERROR)

    return store.llen(key)


def cmd_lindex(store: DataStore, expiry: ExpiryManager, args: List[str]) -> Any:
    """
    LINDEX key index
    특정 인덱스의 원소를 반환합니다.
    반환: 값 (bulk string) 또는 nil (범위 초과)
    """
    if len(args) != 2:
        return _wrong_number("lindex")

    key = args[0]

    if store.exists(key) and store.get_type(key) != "list":
        return RespError(WRONGTYPE_ERROR)

    try:
        index = int(args[1])
    except ValueError:
        return RespError("ERR value is not an integer or out of range")

    return store.lindex(key, index)


def cmd_lset(store: DataStore, expiry: ExpiryManager, args: List[str]) -> Any:
    """
    LSET key index value
    특정 인덱스의 원소를 변경합니다.
    반환: +OK 또는 오류 (인덱스 범위 초과)
    """
    if len(args) != 3:
        return _wrong_number("lset")

    key = args[0]

    if store.exists(key) and store.get_type(key) != "list":
        return RespError(WRONGTYPE_ERROR)

    try:
        index = int(args[1])
    except ValueError:
        return RespError("ERR value is not an integer or out of range")

    try:
        store.lset(key, index, args[2])
    except KeyError:
        return RespError("ERR no such key")
    except IndexError:
        return RespError("ERR index out of range")
    return SimpleString("OK")

"""
String 명령어 핸들러 (팀원 C 담당)

모든 함수는 동일한 시그니처를 가집니다:
  (store, expiry, args) → Any

반환값은 Python 값으로, server.py의 encode()가 RESP 바이트로 변환합니다.
  성공 메시지  → SimpleString("OK")
  오류        → RespError("ERR ...")
  문자열      → str 또는 None
  숫자        → int
  목록        → list

args: 명령어 뒤의 인자 리스트 (명령어 이름 제외)
예: "SET foo bar" → args = ["foo", "bar"]
"""

from typing import List, Any
from store.datastore import DataStore
from store.expiry import ExpiryManager
from store.redis_object import TYPE_STRING, make_string
from protocol.encoder import SimpleString, RespError


def cmd_get(store, expiry, args):
    if len(args) != 1:
        return RespError("ERR wrong number of arguments")

    key = args[0]

    if expiry.is_expired(key):
        store.delete(key)
        return None

    obj = store.get(key)

    if obj is None:
        return None

    return obj.value


def cmd_set(store, expiry, args):
    if len(args) < 2:
        return RespError("ERR wrong number of arguments")

    key = args[0]
    value = args[1]

    # 저장
    obj = make_string(value)
    store.set(key, obj)

    # 기존 TTL 제거
    expiry.remove_expiry(key)

    # EX 옵션만 최소 처리 (지금 단계)
    if len(args) >= 4 and args[2].upper() == "EX":
        seconds = int(args[3])
        expiry.set_expiry(key, float(seconds))

    return "OK"


def cmd_mget(store: DataStore, expiry: ExpiryManager, args: List[str]) -> Any:
    result = []

    for key in args:
        if expiry.is_expired(key):
            store.delete(key)
            result.append(None)
            continue

        obj = store.get(key)
        if obj is None:
            result.append(None)
        else:
            result.append(obj.value)

    return result


def cmd_mset(store: DataStore, expiry: ExpiryManager, args: List[str]) -> Any:
    if len(args) % 2 != 0:
        return RespError("ERR wrong number of arguments for 'mset' command")

    for i in range(0, len(args), 2):
        key = args[i]
        value = args[i + 1]

        store.set(key, make_string(value))
        expiry.remove_expiry(key)

    return "OK"


def cmd_incr(store: DataStore, expiry: ExpiryManager, args: List[str]) -> Any:
    if len(args) != 1:
        return RespError("ERR wrong number of arguments for 'incr' command")

    key = args[0]

    if expiry.is_expired(key):
        store.delete(key)

    obj = store.get(key)

    if obj is None:
        value = 1
    else:
        try:
            value = int(obj.value) + 1
        except:
            return RespError("ERR value is not an integer")

    store.set(key, make_string(str(value)))
    return value


def cmd_decr(store: DataStore, expiry: ExpiryManager, args: List[str]) -> Any:
    if len(args) != 1:
        return RespError("ERR wrong number of arguments for 'decr' command")

    key = args[0]

    if expiry.is_expired(key):
        store.delete(key)

    obj = store.get(key)

    if obj is None:
        value = -1
    else:
        try:
            value = int(obj.value) - 1
        except:
            return RespError("ERR value is not an integer")

    store.set(key, make_string(str(value)))
    return value


def cmd_incrby(store: DataStore, expiry: ExpiryManager, args: List[str]) -> Any:
    if len(args) != 2:
        return RespError("ERR wrong number of arguments for 'incrby' command")

    key = args[0]

    try:
        increment = int(args[1])
    except:
        return RespError("ERR increment is not an integer")

    if expiry.is_expired(key):
        store.delete(key)

    obj = store.get(key)

    if obj is None:
        value = increment
    else:
        try:
            value = int(obj.value) + increment
        except:
            return RespError("ERR value is not an integer")

    store.set(key, make_string(str(value)))
    return value


def cmd_append(store: DataStore, expiry: ExpiryManager, args: List[str]) -> Any:
    if len(args) != 2:
        return RespError("ERR wrong number of arguments for 'append' command")

    key = args[0]
    append_value = args[1]

    if expiry.is_expired(key):
        store.delete(key)

    obj = store.get(key)

    if obj is None:
        new_value = append_value
    else:
        new_value = obj.value + append_value

    store.set(key, make_string(new_value))
    return len(new_value)


def cmd_strlen(store: DataStore, expiry: ExpiryManager, args: List[str]) -> Any:
    if len(args) != 1:
        return RespError("ERR wrong number of arguments for 'strlen' command")

    key = args[0]

    if expiry.is_expired(key):
        store.delete(key)
        return 0

    obj = store.get(key)

    if obj is None:
        return 0

    return len(obj.value)

def cmd_mget(store: DataStore, expiry: ExpiryManager, args: List[str]) -> Any:
    result = []

    for key in args:
        if expiry.is_expired(key):
            store.delete(key)
            result.append(None)
            continue

        obj = store.get(key)
        if obj is None:
            result.append(None)
        else:
            result.append(obj.value)

    return result


def cmd_mset(store: DataStore, expiry: ExpiryManager, args: List[str]) -> Any:
    if len(args) % 2 != 0:
        return RespError("ERR wrong number of arguments for 'mset' command")

    for i in range(0, len(args), 2):
        key = args[i]
        value = args[i + 1]

        store.set(key, make_string(value))
        expiry.remove_expiry(key)

    return "OK"


def cmd_incr(store: DataStore, expiry: ExpiryManager, args: List[str]) -> Any:
    if len(args) != 1:
        return RespError("ERR wrong number of arguments for 'incr' command")

    key = args[0]

    if expiry.is_expired(key):
        store.delete(key)

    obj = store.get(key)

    if obj is None:
        value = 1
    else:
        try:
            value = int(obj.value) + 1
        except:
            return RespError("ERR value is not an integer")

    store.set(key, make_string(str(value)))
    return value


def cmd_decr(store: DataStore, expiry: ExpiryManager, args: List[str]) -> Any:
    if len(args) != 1:
        return RespError("ERR wrong number of arguments for 'decr' command")

    key = args[0]

    if expiry.is_expired(key):
        store.delete(key)

    obj = store.get(key)

    if obj is None:
        value = -1
    else:
        try:
            value = int(obj.value) - 1
        except:
            return RespError("ERR value is not an integer")

    store.set(key, make_string(str(value)))
    return value


def cmd_incrby(store: DataStore, expiry: ExpiryManager, args: List[str]) -> Any:
    if len(args) != 2:
        return RespError("ERR wrong number of arguments for 'incrby' command")

    key = args[0]

    try:
        increment = int(args[1])
    except:
        return RespError("ERR increment is not an integer")

    if expiry.is_expired(key):
        store.delete(key)

    obj = store.get(key)

    if obj is None:
        value = increment
    else:
        try:
            value = int(obj.value) + increment
        except:
            return RespError("ERR value is not an integer")

    store.set(key, make_string(str(value)))
    return value


def cmd_append(store: DataStore, expiry: ExpiryManager, args: List[str]) -> Any:
    if len(args) != 2:
        return RespError("ERR wrong number of arguments for 'append' command")

    key = args[0]
    append_value = args[1]

    if expiry.is_expired(key):
        store.delete(key)

    obj = store.get(key)

    if obj is None:
        new_value = append_value
    else:
        new_value = obj.value + append_value

    store.set(key, make_string(new_value))
    return len(new_value)


def cmd_strlen(store: DataStore, expiry: ExpiryManager, args: List[str]) -> Any:
    if len(args) != 1:
        return RespError("ERR wrong number of arguments for 'strlen' command")

    key = args[0]

    if expiry.is_expired(key):
        store.delete(key)
        return 0

    obj = store.get(key)

    if obj is None:
        return 0

    return len(obj.value)
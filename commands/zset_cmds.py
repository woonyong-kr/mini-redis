"""Sorted-set handlers built on top of the skiplist-backed store path."""

from __future__ import annotations

from typing import List, Any
from store.datastore import DataStore
from store.expiry import ExpiryManager
from protocol.encoder import RespError

WRONGTYPE_ERROR = "WRONGTYPE Operation against a key holding the wrong kind of value"


def _wrong_number(command: str) -> RespError:
    return RespError(f"ERR wrong number of arguments for '{command}' command")


def _type_error(store: DataStore, key: str) -> RespError | None:
    key_type = store.get_type(key)
    if key_type in ("none", "zset"):
        return None
    return RespError(WRONGTYPE_ERROR)


def _format_score(score: float) -> str:
    return format(score, "g")


def _parse_score(raw: str) -> float:
    if raw == "-inf":
        return float("-inf")
    if raw in ("+inf", "inf"):
        return float("inf")
    return float(raw)


def cmd_zadd(store: DataStore, expiry: ExpiryManager, args: List[str]) -> Any:
    """Adds or updates one or more members in a sorted set."""
    if len(args) < 3 or len(args) % 2 == 0:
        return _wrong_number("zadd")

    key = args[0]
    type_error = _type_error(store, key)
    if type_error is not None:
        return type_error

    parsed_pairs = []
    for index in range(1, len(args), 2):
        try:
            score = float(args[index])
        except ValueError:
            return RespError("ERR value is not a valid float")
        parsed_pairs.append((score, args[index + 1]))

    snapshot = store._snapshot_key(key)
    added = 0
    try:
        for score, member in parsed_pairs:
            added += store.zadd(key, score, member)
    except Exception:
        store._restore_key_snapshot(key, snapshot)
        raise
    return added


def cmd_zrem(store: DataStore, expiry: ExpiryManager, args: List[str]) -> Any:
    """Removes one or more members from a sorted set."""
    if len(args) < 2:
        return _wrong_number("zrem")

    key = args[0]
    type_error = _type_error(store, key)
    if type_error is not None:
        return type_error

    removed = 0
    for member in args[1:]:
        removed += store.zrem(key, member)
    return removed


def cmd_zscore(store: DataStore, expiry: ExpiryManager, args: List[str]) -> Any:
    """Returns one member score as a bulk string."""
    if len(args) != 2:
        return _wrong_number("zscore")

    key, member = args
    type_error = _type_error(store, key)
    if type_error is not None:
        return type_error

    score = store.zscore(key, member)
    if score is None:
        return None
    return _format_score(score)


def cmd_zrank(store: DataStore, expiry: ExpiryManager, args: List[str]) -> Any:
    """Returns the ascending rank of one member."""
    if len(args) != 2:
        return _wrong_number("zrank")

    key, member = args
    type_error = _type_error(store, key)
    if type_error is not None:
        return type_error
    return store.zrank(key, member)


def cmd_zrange(store: DataStore, expiry: ExpiryManager, args: List[str]) -> Any:
    """Returns an ascending range, optionally interleaved with scores."""
    if len(args) not in (3, 4):
        return _wrong_number("zrange")

    key = args[0]
    type_error = _type_error(store, key)
    if type_error is not None:
        return type_error

    try:
        start = int(args[1])
        stop = int(args[2])
    except ValueError:
        return RespError("ERR value is not an integer or out of range")

    withscores = len(args) == 4
    if withscores and args[3].upper() != "WITHSCORES":
        return RespError("ERR syntax error")

    if not withscores:
        return store.zrange(key, start, stop)

    result: List[str] = []
    for member, score in store.zrange_withscores(key, start, stop):
        result.append(member)
        result.append(_format_score(score))
    return result


def cmd_zrevrange(store: DataStore, expiry: ExpiryManager, args: List[str]) -> Any:
    """Returns a descending range, optionally interleaved with scores."""
    if len(args) not in (3, 4):
        return _wrong_number("zrevrange")

    key = args[0]
    type_error = _type_error(store, key)
    if type_error is not None:
        return type_error

    try:
        start = int(args[1])
        stop = int(args[2])
    except ValueError:
        return RespError("ERR value is not an integer or out of range")

    withscores = len(args) == 4
    if withscores and args[3].upper() != "WITHSCORES":
        return RespError("ERR syntax error")

    entries = store.zrange_withscores(key, start, stop, reverse=True)
    if not withscores:
        return [member for member, _ in entries]

    result: List[str] = []
    for member, score in entries:
        result.append(member)
        result.append(_format_score(score))
    return result


def cmd_zcard(store: DataStore, expiry: ExpiryManager, args: List[str]) -> Any:
    """Returns the number of members in a sorted set."""
    if len(args) != 1:
        return _wrong_number("zcard")

    key = args[0]
    type_error = _type_error(store, key)
    if type_error is not None:
        return type_error
    return store.zcard(key)


def cmd_zrangebyscore(store: DataStore, expiry: ExpiryManager, args: List[str]) -> Any:
    """Returns members whose scores fall inside the inclusive range."""
    if len(args) != 3:
        return _wrong_number("zrangebyscore")

    key = args[0]
    type_error = _type_error(store, key)
    if type_error is not None:
        return type_error

    try:
        minimum = _parse_score(args[1])
        maximum = _parse_score(args[2])
    except ValueError:
        return RespError("ERR min or max is not a float")

    return store.zrangebyscore(key, minimum, maximum)

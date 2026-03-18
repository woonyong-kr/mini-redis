"""Set command handlers.

These handlers cover membership, cardinality, and basic set algebra while
leaving more advanced blocking or pub/sub style semantics out of scope.
"""

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
    if key_type in ("none", "set"):
        return None
    return RespError(WRONGTYPE_ERROR)


def cmd_sadd(store: DataStore, expiry: ExpiryManager, args: List[str]) -> Any:
    """Adds one or more members to a set."""
    if len(args) < 2:
        return _wrong_number("sadd")

    key = args[0]
    type_error = _type_error(store, key)
    if type_error is not None:
        return type_error
    return store.sadd(key, *args[1:])


def cmd_srem(store: DataStore, expiry: ExpiryManager, args: List[str]) -> Any:
    """Removes one or more members from a set."""
    if len(args) < 2:
        return _wrong_number("srem")

    key = args[0]
    type_error = _type_error(store, key)
    if type_error is not None:
        return type_error
    return store.srem(key, *args[1:])


def cmd_smembers(store: DataStore, expiry: ExpiryManager, args: List[str]) -> Any:
    """Returns all members of a set in sorted order for deterministic replies."""
    if len(args) != 1:
        return _wrong_number("smembers")

    key = args[0]
    type_error = _type_error(store, key)
    if type_error is not None:
        return type_error
    return sorted(store.smembers(key))


def cmd_sismember(store: DataStore, expiry: ExpiryManager, args: List[str]) -> Any:
    """Checks whether one member belongs to a set."""
    if len(args) != 2:
        return _wrong_number("sismember")

    key, member = args
    type_error = _type_error(store, key)
    if type_error is not None:
        return type_error
    return 1 if store.sismember(key, member) else 0


def cmd_scard(store: DataStore, expiry: ExpiryManager, args: List[str]) -> Any:
    """Returns the number of members in a set."""
    if len(args) != 1:
        return _wrong_number("scard")

    key = args[0]
    type_error = _type_error(store, key)
    if type_error is not None:
        return type_error
    return store.scard(key)


def cmd_sinter(store: DataStore, expiry: ExpiryManager, args: List[str]) -> Any:
    """Returns the intersection of multiple sets."""
    if len(args) == 0:
        return _wrong_number("sinter")

    for key in args:
        type_error = _type_error(store, key)
        if type_error is not None:
            return type_error
    return sorted(store.sinter(*args))


def cmd_sunion(store: DataStore, expiry: ExpiryManager, args: List[str]) -> Any:
    """Returns the union of multiple sets."""
    if len(args) == 0:
        return _wrong_number("sunion")

    for key in args:
        type_error = _type_error(store, key)
        if type_error is not None:
            return type_error
    return sorted(store.sunion(*args))


def cmd_sdiff(store: DataStore, expiry: ExpiryManager, args: List[str]) -> Any:
    """Returns the left-to-right set difference."""
    if len(args) == 0:
        return _wrong_number("sdiff")

    for key in args:
        type_error = _type_error(store, key)
        if type_error is not None:
            return type_error
    return sorted(store.sdiff(*args))

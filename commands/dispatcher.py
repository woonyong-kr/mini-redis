"""Maps RESP command names to the handlers used by the core server.

The table is intentionally grouped so the runtime can stay small:
core data commands first, convenience commands next, and persistence-only
helpers such as `PEXPIREAT` last.
"""

from typing import List, Callable, Dict, Any
from store.datastore import DataStore
from store.errors import MemoryLimitError
from store.expiry import ExpiryManager
from protocol.encoder import RespError

HandlerType = Callable[[DataStore, ExpiryManager, List[str]], Any]


def build_command_table() -> Dict[str, HandlerType]:
    """Builds the runtime command table once at import time."""
    from commands.string_cmds import (
        cmd_get, cmd_set, cmd_mget, cmd_mset,
        cmd_incr, cmd_decr, cmd_incrby, cmd_append, cmd_strlen
    )
    from commands.generic_cmds import (
        cmd_ping, cmd_del, cmd_exists, cmd_expire,
        cmd_ttl, cmd_persist, cmd_pexpireat, cmd_type, cmd_keys, cmd_flushall
    )
    from commands.hash_cmds import (
        cmd_hset, cmd_hget, cmd_hmset, cmd_hmget, cmd_hgetall,
        cmd_hdel, cmd_hexists, cmd_hkeys, cmd_hvals, cmd_hlen
    )
    from commands.list_cmds import (
        cmd_lpush, cmd_rpush, cmd_lpop, cmd_rpop,
        cmd_lrange, cmd_llen, cmd_lindex, cmd_lset
    )
    from commands.set_cmds import (
        cmd_sadd, cmd_srem, cmd_smembers, cmd_sismember,
        cmd_scard, cmd_sinter, cmd_sunion, cmd_sdiff
    )
    from commands.zset_cmds import (
        cmd_zadd, cmd_zrem, cmd_zscore, cmd_zrank,
        cmd_zrange, cmd_zrevrange, cmd_zcard, cmd_zrangebyscore
    )

    core_string = {
        "GET": cmd_get,
        "SET": cmd_set,
        "MGET": cmd_mget,
        "MSET": cmd_mset,
        "INCR": cmd_incr,
        "DECR": cmd_decr,
        "INCRBY": cmd_incrby,
    }

    extended_string = {
        "APPEND": cmd_append,
        "STRLEN": cmd_strlen,
    }

    core_generic = {
        "PING": cmd_ping,
        "DEL": cmd_del,
        "EXISTS": cmd_exists,
        "EXPIRE": cmd_expire,
        "TTL": cmd_ttl,
        "PERSIST": cmd_persist,
        "TYPE": cmd_type,
    }

    maintenance_generic = {
        "PEXPIREAT": cmd_pexpireat,
        "KEYS": cmd_keys,
        "FLUSHALL": cmd_flushall,
    }

    core_hash = {
        "HSET": cmd_hset,
        "HGET": cmd_hget,
        "HGETALL": cmd_hgetall,
        "HDEL": cmd_hdel,
        "HEXISTS": cmd_hexists,
        "HLEN": cmd_hlen,
    }

    extended_hash = {
        "HMSET": cmd_hmset,
        "HMGET": cmd_hmget,
        "HKEYS": cmd_hkeys,
        "HVALS": cmd_hvals,
    }

    core_list = {
        "LPUSH": cmd_lpush,
        "RPUSH": cmd_rpush,
        "LPOP": cmd_lpop,
        "RPOP": cmd_rpop,
        "LRANGE": cmd_lrange,
        "LLEN": cmd_llen,
    }

    extended_list = {
        "LINDEX": cmd_lindex,
        "LSET": cmd_lset,
    }

    core_set = {
        "SADD": cmd_sadd,
        "SREM": cmd_srem,
        "SMEMBERS": cmd_smembers,
        "SISMEMBER": cmd_sismember,
        "SCARD": cmd_scard,
    }

    extended_set = {
        "SINTER": cmd_sinter,
        "SUNION": cmd_sunion,
        "SDIFF": cmd_sdiff,
    }

    core_zset = {
        "ZADD": cmd_zadd,
        "ZREM": cmd_zrem,
        "ZSCORE": cmd_zscore,
        "ZRANK": cmd_zrank,
        "ZRANGE": cmd_zrange,
        "ZREVRANGE": cmd_zrevrange,
        "ZCARD": cmd_zcard,
    }

    extended_zset = {
        "ZRANGEBYSCORE": cmd_zrangebyscore,
    }

    table: Dict[str, HandlerType] = {}
    for group in (
        core_string,
        extended_string,
        core_generic,
        maintenance_generic,
        core_hash,
        extended_hash,
        core_list,
        extended_list,
        core_set,
        extended_set,
        core_zset,
        extended_zset,
    ):
        table.update(group)
    return table


COMMAND_TABLE: Dict[str, HandlerType] = build_command_table()


def dispatch(
    command: List[str],
    store: DataStore,
    expiry: ExpiryManager
) -> Any:
    """Runs one parsed command and returns the raw Python result."""
    if not command:
        return RespError("ERR empty command")

    cmd_name = command[0].upper()
    args = command[1:]

    handler = COMMAND_TABLE.get(cmd_name)
    if handler is None:
        return RespError(f"ERR unknown command '{cmd_name}'")

    try:
        return handler(store, expiry, args)
    except MemoryLimitError as e:
        return RespError(str(e))
    except Exception as e:
        return RespError(f"ERR internal error: {str(e)}")

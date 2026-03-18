"""
명령어 디스패처 (리더 담당)

클라이언트로부터 받은 명령어를 적절한 핸들러 함수로 라우팅합니다.
팀원들이 각 명령어를 구현하면, 이 파일에 등록합니다.
"""

from typing import List, Callable, Dict, Any
from store.datastore import DataStore
from store.expiry import ExpiryManager
from protocol.encoder import RespError

# 명령어 핸들러 타입 (bytes 대신 Any 반환 - 인코딩은 server.py에서 담당)
HandlerType = Callable[[DataStore, ExpiryManager, List[str]], Any]


def build_command_table() -> Dict[str, HandlerType]:
    """
    명령어 이름 → 핸들러 함수 매핑 테이블을 생성합니다.
    팀원들이 함수를 구현하면 이 테이블에 추가하세요.
    """
    from commands.string_cmds import (
        cmd_get, cmd_set, cmd_mget, cmd_mset,
        cmd_incr, cmd_decr, cmd_incrby, cmd_append, cmd_strlen
    )
    from commands.generic_cmds import (
        cmd_ping, cmd_del, cmd_exists, cmd_expire,
        cmd_ttl, cmd_persist, cmd_type, cmd_keys, cmd_flushall
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

    return {
        # String
        "GET": cmd_get,
        "SET": cmd_set,
        "MGET": cmd_mget,
        "MSET": cmd_mset,
        "INCR": cmd_incr,
        "DECR": cmd_decr,
        "INCRBY": cmd_incrby,
        "APPEND": cmd_append,
        "STRLEN": cmd_strlen,

        # Generic
        "PING": cmd_ping,
        "DEL": cmd_del,
        "EXISTS": cmd_exists,
        "EXPIRE": cmd_expire,
        "TTL": cmd_ttl,
        "PERSIST": cmd_persist,
        "TYPE": cmd_type,
        "KEYS": cmd_keys,
        "FLUSHALL": cmd_flushall,

        # Hash
        "HSET": cmd_hset,
        "HGET": cmd_hget,
        "HMSET": cmd_hmset,
        "HMGET": cmd_hmget,
        "HGETALL": cmd_hgetall,
        "HDEL": cmd_hdel,
        "HEXISTS": cmd_hexists,
        "HKEYS": cmd_hkeys,
        "HVALS": cmd_hvals,
        "HLEN": cmd_hlen,

        # List
        "LPUSH": cmd_lpush,
        "RPUSH": cmd_rpush,
        "LPOP": cmd_lpop,
        "RPOP": cmd_rpop,
        "LRANGE": cmd_lrange,
        "LLEN": cmd_llen,
        "LINDEX": cmd_lindex,
        "LSET": cmd_lset,

        # Set
        "SADD": cmd_sadd,
        "SREM": cmd_srem,
        "SMEMBERS": cmd_smembers,
        "SISMEMBER": cmd_sismember,
        "SCARD": cmd_scard,
        "SINTER": cmd_sinter,
        "SUNION": cmd_sunion,
        "SDIFF": cmd_sdiff,

        # Sorted Set
        "ZADD": cmd_zadd,
        "ZREM": cmd_zrem,
        "ZSCORE": cmd_zscore,
        "ZRANK": cmd_zrank,
        "ZRANGE": cmd_zrange,
        "ZREVRANGE": cmd_zrevrange,
        "ZCARD": cmd_zcard,
        "ZRANGEBYSCORE": cmd_zrangebyscore,
    }


# 전역 명령어 테이블 (서버 시작 시 한 번 초기화)
COMMAND_TABLE: Dict[str, HandlerType] = build_command_table()


def dispatch(
    command: List[str],
    store: DataStore,
    expiry: ExpiryManager
) -> Any:
    """
    파싱된 명령어를 받아 적절한 핸들러를 실행합니다.
    인코딩은 하지 않고 Python 값을 그대로 반환합니다.
    인코딩은 server.py에서 encode()를 호출해 처리합니다.

    예:
      command = ["SET", "foo", "bar"]
      → cmd_set(store, expiry, ["foo", "bar"]) 호출
      → SimpleString("OK") 반환

    알 수 없는 명령어는 RespError 반환.
    """
    if not command:
        return RespError("ERR empty command")

    cmd_name = command[0].upper()
    args = command[1:]

    handler = COMMAND_TABLE.get(cmd_name)
    if handler is None:
        return RespError(f"ERR unknown command '{cmd_name}'")

    try:
        return handler(store, expiry, args)
    except NotImplementedError:
        return RespError(f"ERR command '{cmd_name}' is not yet implemented")
    except Exception as e:
        return RespError(f"ERR internal error: {str(e)}")

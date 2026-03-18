import pytest

from commands.list_cmds import (
    cmd_lindex,
    cmd_llen,
    cmd_lpop,
    cmd_lpush,
    cmd_lrange,
    cmd_lset,
    cmd_rpop,
    cmd_rpush,
)
from commands.set_cmds import (
    cmd_sadd,
    cmd_scard,
    cmd_sdiff,
    cmd_sinter,
    cmd_sismember,
    cmd_smembers,
    cmd_srem,
    cmd_sunion,
)
from commands.zset_cmds import (
    cmd_zadd,
    cmd_zcard,
    cmd_zrange,
    cmd_zrangebyscore,
    cmd_zrank,
    cmd_zrem,
    cmd_zrevrange,
    cmd_zscore,
)
from protocol.encoder import RespError, SimpleString
from store.datastore import DataStore
from store.expiry import ExpiryManager
from store.redis_object import make_string


@pytest.fixture
def ctx():
    store = DataStore()
    expiry = ExpiryManager(store)
    return store, expiry


class TestListCommands:
    def test_list_push_pop_range_and_len(self, ctx):
        store, expiry = ctx

        assert cmd_lpush(store, expiry, ["letters", "b", "a"]) == 2
        assert cmd_rpush(store, expiry, ["letters", "c"]) == 3
        assert cmd_lrange(store, expiry, ["letters", "0", "-1"]) == ["a", "b", "c"]
        assert cmd_llen(store, expiry, ["letters"]) == 3
        assert cmd_lindex(store, expiry, ["letters", "-1"]) == "c"
        assert cmd_lset(store, expiry, ["letters", "1", "beta"]) == SimpleString("OK")
        assert cmd_lrange(store, expiry, ["letters", "0", "-1"]) == ["a", "beta", "c"]
        assert cmd_lpop(store, expiry, ["letters"]) == "a"
        assert cmd_rpop(store, expiry, ["letters"]) == "c"

    def test_lset_reports_missing_and_out_of_range(self, ctx):
        store, expiry = ctx

        assert cmd_lset(store, expiry, ["missing", "0", "value"]) == RespError("ERR no such key")
        cmd_rpush(store, expiry, ["letters", "a"])
        assert cmd_lset(store, expiry, ["letters", "5", "value"]) == RespError(
            "ERR index out of range"
        )


class TestSetCommands:
    def test_set_add_remove_membership_and_set_ops(self, ctx):
        store, expiry = ctx

        assert cmd_sadd(store, expiry, ["set:1", "a", "b", "a"]) == 2
        assert cmd_sadd(store, expiry, ["set:2", "b", "c"]) == 2
        assert sorted(cmd_smembers(store, expiry, ["set:1"])) == ["a", "b"]
        assert cmd_sismember(store, expiry, ["set:1", "a"]) == 1
        assert cmd_scard(store, expiry, ["set:1"]) == 2
        assert cmd_sinter(store, expiry, ["set:1", "set:2"]) == ["b"]
        assert cmd_sunion(store, expiry, ["set:1", "set:2"]) == ["a", "b", "c"]
        assert cmd_sdiff(store, expiry, ["set:1", "set:2"]) == ["a"]
        assert cmd_srem(store, expiry, ["set:1", "a", "missing"]) == 1


class TestZSetCommands:
    def test_zset_basic_commands(self, ctx):
        store, expiry = ctx

        assert cmd_zadd(store, expiry, ["board", "10", "alice", "20", "bob", "15", "carol"]) == 3
        assert cmd_zadd(store, expiry, ["board", "25", "bob"]) == 0
        assert cmd_zscore(store, expiry, ["board", "alice"]) == "10"
        assert cmd_zrank(store, expiry, ["board", "bob"]) == 2
        assert cmd_zcard(store, expiry, ["board"]) == 3
        assert cmd_zrange(store, expiry, ["board", "0", "-1"]) == ["alice", "carol", "bob"]
        assert cmd_zrange(store, expiry, ["board", "0", "-1", "WITHSCORES"]) == [
            "alice",
            "10",
            "carol",
            "15",
            "bob",
            "25",
        ]
        assert cmd_zrevrange(store, expiry, ["board", "0", "1"]) == ["bob", "carol"]
        assert cmd_zrangebyscore(store, expiry, ["board", "10", "20"]) == ["alice", "carol"]
        assert cmd_zrem(store, expiry, ["board", "carol", "missing"]) == 1

    def test_collection_commands_report_wrongtype(self, ctx):
        store, expiry = ctx
        store.set("plain", make_string("value"))

        wrongtype = "WRONGTYPE Operation against a key holding the wrong kind of value"
        assert cmd_sadd(store, expiry, ["plain", "x"]) == RespError(wrongtype)
        assert cmd_zadd(store, expiry, ["plain", "1", "x"]) == RespError(wrongtype)
        assert cmd_lindex(store, expiry, ["plain", "0"]) == RespError(wrongtype)

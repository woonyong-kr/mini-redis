import pytest

from commands.string_cmds import (
    cmd_append,
    cmd_decr,
    cmd_get,
    cmd_incr,
    cmd_incrby,
    cmd_mget,
    cmd_mset,
    cmd_set,
    cmd_strlen,
)
from commands.generic_cmds import cmd_ping, cmd_del, cmd_exists, cmd_ttl, cmd_expire
from protocol.encoder import SimpleString, RespError
from store.datastore import DataStore
from store.expiry import ExpiryManager


@pytest.fixture
def ctx():
    store = DataStore()
    expiry = ExpiryManager(store)
    return store, expiry


class TestPing:
    def test_ping_no_arg(self, ctx):
        store, expiry = ctx
        assert cmd_ping(store, expiry, []) == SimpleString("PONG")

    def test_ping_with_message(self, ctx):
        store, expiry = ctx
        assert cmd_ping(store, expiry, ["hello"]) == "hello"

    def test_ping_too_many_args(self, ctx):
        store, expiry = ctx
        result = cmd_ping(store, expiry, ["hello", "again"])
        assert result == RespError("ERR wrong number of arguments for 'ping' command")


class TestSetGet:
    def test_set_and_get(self, ctx):
        store, expiry = ctx
        assert cmd_set(store, expiry, ["foo", "bar"]) == SimpleString("OK")
        assert cmd_get(store, expiry, ["foo"]) == b"bar"

    def test_get_missing_key(self, ctx):
        store, expiry = ctx
        assert cmd_get(store, expiry, ["missing"]) is None

    def test_set_overwrites(self, ctx):
        store, expiry = ctx
        cmd_set(store, expiry, ["foo", "bar"])
        cmd_set(store, expiry, ["foo", "baz"])
        assert cmd_get(store, expiry, ["foo"]) == b"baz"

    def test_set_with_expiry(self, ctx):
        store, expiry = ctx
        cmd_set(store, expiry, ["foo", "bar", "EX", "100"])
        assert expiry.get_ttl("foo") > 0

    def test_invalid_set_does_not_mutate_existing_value(self, ctx):
        store, expiry = ctx
        cmd_set(store, expiry, ["foo", "safe"])

        result = cmd_set(store, expiry, ["foo", "unsafe", "PX", "0"])

        assert result == RespError("ERR invalid expire time in 'set' command")
        assert cmd_get(store, expiry, ["foo"]) == b"safe"

    def test_invalid_set_does_not_create_key(self, ctx):
        store, expiry = ctx

        result = cmd_set(store, expiry, ["foo", "bar", "BADOPT"])

        assert result == RespError("ERR syntax error")
        assert cmd_get(store, expiry, ["foo"]) is None


class TestStringCommands:
    def test_mset_and_mget(self, ctx):
        store, expiry = ctx

        assert cmd_mset(store, expiry, ["k1", "v1", "k2", "v2"]) == SimpleString("OK")
        assert cmd_mget(store, expiry, ["k1", "missing", "k2"]) == [b"v1", None, b"v2"]

    def test_mset_rejects_odd_arity(self, ctx):
        store, expiry = ctx
        assert cmd_mset(store, expiry, ["k1", "v1", "k2"]) == RespError(
            "ERR wrong number of arguments for 'mset' command"
        )

    def test_incr_new_key(self, ctx):
        store, expiry = ctx
        assert cmd_incr(store, expiry, ["counter"]) == 1

    def test_incr_existing(self, ctx):
        store, expiry = ctx
        cmd_set(store, expiry, ["counter", "10"])
        assert cmd_incr(store, expiry, ["counter"]) == 11

    def test_decr(self, ctx):
        store, expiry = ctx
        cmd_set(store, expiry, ["counter", "5"])
        assert cmd_decr(store, expiry, ["counter"]) == 4

    def test_append(self, ctx):
        store, expiry = ctx
        cmd_set(store, expiry, ["foo", "bar"])
        assert cmd_append(store, expiry, ["foo", "baz"]) == 6
        assert cmd_get(store, expiry, ["foo"]) == b"barbaz"

    def test_incrby(self, ctx):
        store, expiry = ctx
        cmd_set(store, expiry, ["counter", "10"])
        assert cmd_incrby(store, expiry, ["counter", "7"]) == 17

    def test_strlen(self, ctx):
        store, expiry = ctx
        cmd_set(store, expiry, ["foo", "hello"])
        assert cmd_strlen(store, expiry, ["foo"]) == 5
        assert cmd_strlen(store, expiry, ["missing"]) == 0

    def test_incr_rejects_non_integer_value(self, ctx):
        store, expiry = ctx
        cmd_set(store, expiry, ["counter", "abc"])
        assert cmd_incr(store, expiry, ["counter"]) == RespError(
            "ERR value is not an integer or out of range"
        )


class TestGenericCommands:
    def test_del_existing(self, ctx):
        store, expiry = ctx
        cmd_set(store, expiry, ["foo", "bar"])
        assert cmd_del(store, expiry, ["foo"]) == 1

    def test_del_missing(self, ctx):
        store, expiry = ctx
        assert cmd_del(store, expiry, ["missing"]) == 0

    def test_exists(self, ctx):
        store, expiry = ctx
        cmd_set(store, expiry, ["foo", "bar"])
        assert cmd_exists(store, expiry, ["foo"]) == 1
        assert cmd_exists(store, expiry, ["missing"]) == 0

    def test_ttl(self, ctx):
        store, expiry = ctx
        cmd_set(store, expiry, ["foo", "bar", "EX", "100"])
        assert cmd_ttl(store, expiry, ["foo"]) >= 0

    def test_expire(self, ctx):
        store, expiry = ctx
        cmd_set(store, expiry, ["foo", "bar"])
        assert cmd_expire(store, expiry, ["foo", "10"]) == 1

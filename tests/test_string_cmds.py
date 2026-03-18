import pytest

from store.datastore import DataStore
from store.expiry import ExpiryManager
from commands.string_cmds import cmd_get, cmd_set, cmd_incr, cmd_decr, cmd_append
from commands.generic_cmds import cmd_ping, cmd_del, cmd_exists, cmd_ttl, cmd_expire
from protocol.encoder import SimpleString, RespError


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
        assert cmd_get(store, expiry, ["foo"]) == "bar"

    def test_get_missing_key(self, ctx):
        store, expiry = ctx
        assert cmd_get(store, expiry, ["missing"]) is None

    def test_set_overwrites(self, ctx):
        store, expiry = ctx
        cmd_set(store, expiry, ["foo", "bar"])
        cmd_set(store, expiry, ["foo", "baz"])
        assert cmd_get(store, expiry, ["foo"]) == "baz"

    def test_set_with_expiry(self, ctx):
        store, expiry = ctx
        cmd_set(store, expiry, ["foo", "bar", "EX", "100"])
        assert expiry.get_ttl("foo") > 0

    def test_invalid_set_does_not_mutate_existing_value(self, ctx):
        store, expiry = ctx
        cmd_set(store, expiry, ["foo", "safe"])

        result = cmd_set(store, expiry, ["foo", "unsafe", "PX", "0"])

        assert result == RespError("ERR invalid expire time in 'set' command")
        assert cmd_get(store, expiry, ["foo"]) == "safe"

    def test_invalid_set_does_not_create_key(self, ctx):
        store, expiry = ctx

        result = cmd_set(store, expiry, ["foo", "bar", "BADOPT"])

        assert result == RespError("ERR syntax error")
        assert cmd_get(store, expiry, ["foo"]) is None


class TestStringNumericAndAppendCommands:
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


class TestGenericKeyCommands:
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

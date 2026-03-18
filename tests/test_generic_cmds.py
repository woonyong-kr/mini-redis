import pytest

from commands.generic_cmds import (
    cmd_del,
    cmd_exists,
    cmd_expire,
    cmd_flushall,
    cmd_keys,
    cmd_persist,
    cmd_ping,
    cmd_ttl,
    cmd_type,
)
from protocol.encoder import RespError, encode
from store.datastore import DataStore
from store.expiry import ExpiryManager


@pytest.fixture
def ctx():
    store = DataStore()
    expiry = ExpiryManager(store)
    return store, expiry


class TestPing:
    def test_ping_without_message(self, ctx):
        store, expiry = ctx
        assert encode(cmd_ping(store, expiry, [])) == b"+PONG\r\n"

    def test_ping_with_message(self, ctx):
        store, expiry = ctx
        assert encode(cmd_ping(store, expiry, ["hello"])) == b"$5\r\nhello\r\n"

    def test_ping_wrong_number_of_arguments(self, ctx):
        store, expiry = ctx
        result = cmd_ping(store, expiry, ["a", "b"])
        assert isinstance(result, RespError)
        assert str(result) == "ERR wrong number of arguments for 'ping' command"


class TestDeleteAndExists:
    def test_del_counts_deleted_keys(self, ctx):
        store, expiry = ctx
        store.set("foo", "bar")
        store.set("baz", "qux")

        assert cmd_del(store, expiry, ["foo", "missing", "baz"]) == 2
        assert store.exists("foo") is False
        assert store.exists("baz") is False

    def test_exists_counts_duplicates(self, ctx):
        store, expiry = ctx
        store.set("foo", "bar")

        assert cmd_exists(store, expiry, ["foo", "foo", "missing"]) == 2


class TestExpiryCommands:
    def test_expire_ttl_and_persist_flow(self, ctx):
        store, expiry = ctx
        store.set("foo", "bar")

        assert cmd_ttl(store, expiry, ["foo"]) == -1
        assert cmd_expire(store, expiry, ["foo", "100"]) == 1
        ttl = cmd_ttl(store, expiry, ["foo"])
        assert isinstance(ttl, int)
        assert 0 <= ttl <= 100
        assert cmd_persist(store, expiry, ["foo"]) == 1
        assert cmd_ttl(store, expiry, ["foo"]) == -1

    def test_expire_missing_key_returns_zero(self, ctx):
        store, expiry = ctx
        assert cmd_expire(store, expiry, ["missing", "10"]) == 0

    def test_expire_rejects_non_integer(self, ctx):
        store, expiry = ctx
        store.set("foo", "bar")

        result = cmd_expire(store, expiry, ["foo", "abc"])
        assert isinstance(result, RespError)
        assert str(result) == "ERR value is not an integer or out of range"

    def test_ttl_treats_expired_key_as_missing(self, ctx):
        store, expiry = ctx
        store.set("foo", "bar")
        expiry.set_expiry("foo", -1)

        assert cmd_ttl(store, expiry, ["foo"]) == -2
        assert store.exists("foo") is False

    def test_delete_cleans_up_expiry_metadata(self, ctx):
        store, expiry = ctx
        store.set("foo", "bar")
        expiry.set_expiry("foo", 100)

        assert cmd_del(store, expiry, ["foo"]) == 1
        assert cmd_ttl(store, expiry, ["foo"]) == -2


class TestTypeKeysFlushall:
    def test_type_and_keys_filter_expired_entries(self, ctx):
        store, expiry = ctx
        store.set("plain", "text")
        store.hset("user:1", "name", "alice")
        store.set("temp", "gone")
        expiry.set_expiry("temp", -1)

        assert encode(cmd_type(store, expiry, ["plain"])) == b"+string\r\n"
        assert encode(cmd_type(store, expiry, ["user:1"])) == b"+hash\r\n"
        assert encode(cmd_type(store, expiry, ["temp"])) == b"+none\r\n"
        assert sorted(cmd_keys(store, expiry, ["*"])) == ["plain", "user:1"]
        assert cmd_keys(store, expiry, ["user:*"]) == ["user:1"]

    def test_flushall_clears_store_and_expiry(self, ctx):
        store, expiry = ctx
        store.set("foo", "bar")
        store.set("bar", "baz")
        expiry.set_expiry("foo", 100)
        expiry.set_expiry("bar", 100)

        assert encode(cmd_flushall(store, expiry, [])) == b"+OK\r\n"
        assert cmd_keys(store, expiry, ["*"]) == []
        assert expiry._expiry == {}

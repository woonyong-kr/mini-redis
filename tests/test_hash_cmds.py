import pytest

from commands.hash_cmds import (
    cmd_hdel,
    cmd_hexists,
    cmd_hget,
    cmd_hgetall,
    cmd_hkeys,
    cmd_hlen,
    cmd_hmget,
    cmd_hmset,
    cmd_hset,
    cmd_hvals,
    WRONGTYPE_ERROR,
)
from protocol.encoder import RespError, SimpleString, encode
from store.datastore import DataStore, TYPE_NONE
from store.expiry import ExpiryManager
from store.hash_table import Hash
from store.redis_object import make_string


@pytest.fixture
def ctx():
    store = DataStore()
    expiry = ExpiryManager(store)
    return store, expiry


def _pair_list(items: list[str]) -> list[tuple[str, str]]:
    return list(zip(items[::2], items[1::2]))


class TestHashCommands:
    def test_hset_hget_update_and_hlen(self, ctx):
        store, expiry = ctx

        assert cmd_hset(store, expiry, ["user:1", "name", "alice"]) == 1
        assert cmd_hset(store, expiry, ["user:1", "name", "bob"]) == 0
        assert cmd_hget(store, expiry, ["user:1", "name"]) == "bob"
        assert cmd_hget(store, expiry, ["user:1", "missing"]) is None
        assert cmd_hlen(store, expiry, ["user:1"]) == 1
        assert encode(cmd_hget(store, expiry, ["user:1", "name"])) == b"$3\r\nbob\r\n"

    def test_hmset_hmget_and_hgetall(self, ctx):
        store, expiry = ctx

        assert cmd_hmset(
            store,
            expiry,
            ["user:2", "name", "alice", "role", "admin", "lang", "python"],
        ) == SimpleString("OK")

        assert cmd_hmget(store, expiry, ["user:2", "name", "missing", "lang"]) == [
            "alice",
            None,
            "python",
        ]

        all_items = cmd_hgetall(store, expiry, ["user:2"])
        assert sorted(_pair_list(all_items)) == [
            ("lang", "python"),
            ("name", "alice"),
            ("role", "admin"),
        ]

    def test_hdel_removes_fields_and_deletes_empty_hash_key(self, ctx):
        store, expiry = ctx

        cmd_hmset(store, expiry, ["user:3", "name", "alice", "role", "admin"])

        assert cmd_hdel(store, expiry, ["user:3", "name"]) == 1
        assert cmd_hlen(store, expiry, ["user:3"]) == 1
        assert cmd_hdel(store, expiry, ["user:3", "role"]) == 1
        assert store.get_type("user:3") == TYPE_NONE
        assert cmd_hdel(store, expiry, ["user:3", "role"]) == 0

    def test_hexists_hkeys_hvals_missing_key(self, ctx):
        store, expiry = ctx

        cmd_hmset(store, expiry, ["user:4", "name", "alice", "role", "admin"])

        assert cmd_hexists(store, expiry, ["user:4", "name"]) == 1
        assert cmd_hexists(store, expiry, ["user:4", "missing"]) == 0
        assert sorted(cmd_hkeys(store, expiry, ["user:4"])) == ["name", "role"]
        assert sorted(cmd_hvals(store, expiry, ["user:4"])) == ["admin", "alice"]
        assert cmd_hkeys(store, expiry, ["missing"]) == []
        assert cmd_hvals(store, expiry, ["missing"]) == []

    def test_hash_commands_preserve_behavior_after_promotion(self, ctx):
        store, expiry = ctx

        for index in range(33):
            assert cmd_hset(
                store, expiry, ["big-hash", f"field-{index}", f"value-{index}"]
            ) == 1

        hash_obj = store.get("big-hash")
        assert hash_obj is not None
        hash_value = hash_obj.value
        assert isinstance(hash_value, Hash)
        assert hash_value.is_compact is False
        assert cmd_hlen(store, expiry, ["big-hash"]) == 33
        assert cmd_hmget(
            store, expiry, ["big-hash", "field-0", "field-16", "field-32"]
        ) == ["value-0", "value-16", "value-32"]

    def test_hash_promotes_on_large_value_threshold(self, ctx):
        store, expiry = ctx

        large_value = "x" * 65
        assert cmd_hset(store, expiry, ["large-hash", "field", large_value]) == 1

        hash_obj = store.get("large-hash")
        assert hash_obj is not None
        hash_value = hash_obj.value
        assert isinstance(hash_value, Hash)
        assert hash_value.is_compact is False
        assert cmd_hget(store, expiry, ["large-hash", "field"]) == large_value

    def test_wrongtype_error_for_hash_commands(self, ctx):
        store, expiry = ctx
        store.set("plain", make_string("string-value"))

        result = cmd_hget(store, expiry, ["plain", "field"])

        assert isinstance(result, RespError)
        assert str(result) == WRONGTYPE_ERROR
        assert encode(result) == f"-{WRONGTYPE_ERROR}\r\n".encode()

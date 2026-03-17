"""
팀원 C 테스트 - commands/string_cmds.py, commands/generic_cmds.py

구현 후 아래 명령어로 테스트:
  pytest tests/test_string_cmds.py -v
"""

import pytest
from store.datastore import DataStore
from store.expiry import ExpiryManager
from commands.string_cmds import cmd_get, cmd_set, cmd_incr, cmd_decr, cmd_append
from commands.generic_cmds import cmd_ping, cmd_del, cmd_exists, cmd_ttl, cmd_expire
from protocol.encoder import encode_simple_string, encode_bulk_string, encode_integer


@pytest.fixture
def ctx():
    """테스트용 store, expiry 생성"""
    store = DataStore()
    expiry = ExpiryManager(store)
    return store, expiry


class TestPing:
    def test_ping_no_arg(self, ctx):
        store, expiry = ctx
        assert cmd_ping(store, expiry, []) == b"+PONG\r\n"

    def test_ping_with_message(self, ctx):
        store, expiry = ctx
        assert cmd_ping(store, expiry, ["hello"]) == b"$5\r\nhello\r\n"


class TestSetGet:
    def test_set_and_get(self, ctx):
        store, expiry = ctx
        cmd_set(store, expiry, ["foo", "bar"])
        assert cmd_get(store, expiry, ["foo"]) == b"$3\r\nbar\r\n"

    def test_get_missing_key(self, ctx):
        store, expiry = ctx
        assert cmd_get(store, expiry, ["missing"]) == b"$-1\r\n"

    def test_set_overwrites(self, ctx):
        store, expiry = ctx
        cmd_set(store, expiry, ["foo", "bar"])
        cmd_set(store, expiry, ["foo", "baz"])
        assert cmd_get(store, expiry, ["foo"]) == b"$3\r\nbaz\r\n"

    def test_set_with_expiry(self, ctx):
        store, expiry = ctx
        cmd_set(store, expiry, ["foo", "bar", "EX", "100"])
        ttl_resp = cmd_ttl(store, expiry, ["foo"])
        # TTL이 0보다 큰 정수여야 함
        assert ttl_resp.startswith(b":")


class TestIncr:
    def test_incr_new_key(self, ctx):
        store, expiry = ctx
        assert cmd_incr(store, expiry, ["counter"]) == b":1\r\n"

    def test_incr_existing(self, ctx):
        store, expiry = ctx
        cmd_set(store, expiry, ["counter", "10"])
        assert cmd_incr(store, expiry, ["counter"]) == b":11\r\n"

    def test_decr(self, ctx):
        store, expiry = ctx
        cmd_set(store, expiry, ["counter", "5"])
        assert cmd_decr(store, expiry, ["counter"]) == b":4\r\n"


class TestDel:
    def test_del_existing(self, ctx):
        store, expiry = ctx
        cmd_set(store, expiry, ["foo", "bar"])
        assert cmd_del(store, expiry, ["foo"]) == b":1\r\n"
        assert cmd_get(store, expiry, ["foo"]) == b"$-1\r\n"

    def test_del_missing(self, ctx):
        store, expiry = ctx
        assert cmd_del(store, expiry, ["missing"]) == b":0\r\n"

    def test_exists(self, ctx):
        store, expiry = ctx
        cmd_set(store, expiry, ["foo", "bar"])
        assert cmd_exists(store, expiry, ["foo"]) == b":1\r\n"
        assert cmd_exists(store, expiry, ["missing"]) == b":0\r\n"

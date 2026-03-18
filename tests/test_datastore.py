import pytest

from store.datastore import DataStore
from store.expiry import ExpiryManager
from store.redis_object import make_string


@pytest.fixture
def ctx():
    store = DataStore()
    expiry = ExpiryManager(store)
    return store, expiry


class TestListMethods:
    def test_list_push_pop_range_and_length(self, ctx):
        store, _ = ctx

        assert store.rpush("numbers", "1", "2") == 2
        assert store.lpush("numbers", "0") == 3
        assert store.llen("numbers") == 3
        assert store.lrange("numbers", 0, -1) == ["0", "1", "2"]
        assert store.lrange("numbers", -2, -1) == ["1", "2"]

        assert store.lpop("numbers") == "0"
        assert store.rpop("numbers") == "2"
        assert store.llen("numbers") == 1
        assert store.rpop("numbers") == "1"
        assert store.exists("numbers") is False

    def test_list_missing_key_behaves_like_empty(self, ctx):
        store, _ = ctx

        assert store.lpop("missing") is None
        assert store.rpop("missing") is None
        assert store.lrange("missing", 0, -1) == []
        assert store.llen("missing") == 0

    def test_list_wrong_type_raises(self, ctx):
        store, _ = ctx
        store.set("plain", make_string("value"))

        with pytest.raises(TypeError, match="WRONGTYPE"):
            store.lpush("plain", "x")


class TestSetMethods:
    def test_set_add_remove_membership_and_cardinality(self, ctx):
        store, _ = ctx

        assert store.sadd("tags", "python", "redis", "python") == 2
        assert store.scard("tags") == 2
        assert store.sismember("tags", "python") is True
        assert store.sismember("tags", "java") is False
        assert store.smembers("tags") == {"python", "redis"}

        assert store.srem("tags", "python", "missing") == 1
        assert store.smembers("tags") == {"redis"}
        assert store.srem("tags", "redis") == 1
        assert store.exists("tags") is False

    def test_set_missing_key_behaves_like_empty(self, ctx):
        store, _ = ctx

        assert store.srem("missing", "member") == 0
        assert store.smembers("missing") == set()
        assert store.sismember("missing", "member") is False
        assert store.scard("missing") == 0

    def test_set_wrong_type_raises(self, ctx):
        store, _ = ctx
        store.set("plain", make_string("value"))

        with pytest.raises(TypeError, match="WRONGTYPE"):
            store.sadd("plain", "x")


class TestZSetMethods:
    def test_zset_add_update_score_range_rank_and_remove(self, ctx):
        store, _ = ctx

        assert store.zadd("scores", 2.0, "bob") == 1
        assert store.zadd("scores", 1.0, "alice") == 1
        assert store.zadd("scores", 2.0, "carol") == 1
        assert store.zadd("scores", 3.0, "bob") == 0

        assert store.zscore("scores", "alice") == 1.0
        assert store.zscore("scores", "bob") == 3.0
        assert store.zrange("scores", 0, -1) == ["alice", "carol", "bob"]
        assert store.zrange("scores", -2, -1) == ["carol", "bob"]
        assert store.zrank("scores", "alice") == 0
        assert store.zrank("scores", "bob") == 2

        assert store.zrem("scores", "carol") == 1
        assert store.zrange("scores", 0, -1) == ["alice", "bob"]
        assert store.zrem("scores", "alice") == 1
        assert store.zrem("scores", "bob") == 1
        assert store.exists("scores") is False

    def test_zset_missing_key_behaves_like_empty(self, ctx):
        store, _ = ctx

        assert store.zrem("missing", "member") == 0
        assert store.zscore("missing", "member") is None
        assert store.zrange("missing", 0, -1) == []
        assert store.zrank("missing", "member") is None

    def test_zset_wrong_type_raises(self, ctx):
        store, _ = ctx
        store.set("plain", make_string("value"))

        with pytest.raises(TypeError, match="WRONGTYPE"):
            store.zadd("plain", 1.0, "member")

"""
Sorted Set 명령어 핸들러 (팀원 E 담당)
"""

from typing import List, Any
from store.datastore import DataStore
from store.expiry import ExpiryManager
from protocol.encoder import SimpleString, RespError

WRONGTYPE_ERROR = "WRONGTYPE Operation against a key holding the wrong kind of value"


def cmd_zadd(store: DataStore, expiry: ExpiryManager, args: List[str]) -> Any:
    """
    ZADD key score member [score member ...]
    반환: 새로 추가된 멤버 수 (integer)

    힌트:
      - args = ["myset", "100", "alice", "200", "bob"]
      - score는 float으로 변환
    """
    raise NotImplementedError


def cmd_zrem(store: DataStore, expiry: ExpiryManager, args: List[str]) -> Any:
    """
    ZREM key member [member ...]
    반환: 삭제된 멤버 수 (integer)
    """
    raise NotImplementedError


def cmd_zscore(store: DataStore, expiry: ExpiryManager, args: List[str]) -> Any:
    """
    ZSCORE key member
    반환: score (bulk string 형태의 숫자) 또는 nil
    주의: score는 숫자지만 Redis는 bulk string으로 반환합니다.
    """
    raise NotImplementedError


def cmd_zrank(store: DataStore, expiry: ExpiryManager, args: List[str]) -> Any:
    """
    ZRANK key member
    score 오름차순 기준 순위(0부터)를 반환합니다.
    반환: 순위 (integer) 또는 nil (멤버 없음)
    """
    raise NotImplementedError


def cmd_zrange(store: DataStore, expiry: ExpiryManager, args: List[str]) -> Any:
    """
    ZRANGE key start stop [WITHSCORES]
    score 오름차순으로 start~stop 범위의 멤버를 반환합니다.
    WITHSCORES 옵션: [member1, score1, member2, score2, ...] 형태 반환
    반환: 배열 (array)
    """
    raise NotImplementedError


def cmd_zrevrange(store: DataStore, expiry: ExpiryManager, args: List[str]) -> Any:
    """
    ZREVRANGE key start stop [WITHSCORES]
    score 내림차순으로 반환합니다.
    """
    raise NotImplementedError


def cmd_zcard(store: DataStore, expiry: ExpiryManager, args: List[str]) -> Any:
    """
    ZCARD key
    반환: 멤버 수 (integer)
    """
    raise NotImplementedError


def cmd_zrangebyscore(store: DataStore, expiry: ExpiryManager, args: List[str]) -> Any:
    """
    ZRANGEBYSCORE key min max
    min~max score 범위의 멤버를 반환합니다.
    반환: 배열 (array)
    힌트: -inf, +inf 문자열도 지원해야 합니다.
    """
    raise NotImplementedError

"""
Set 명령어 핸들러 (팀원 E 담당)
"""

from typing import List, Any
from store.datastore import DataStore
from store.expiry import ExpiryManager
from protocol.encoder import SimpleString, RespError

WRONGTYPE_ERROR = "WRONGTYPE Operation against a key holding the wrong kind of value"


def cmd_sadd(store: DataStore, expiry: ExpiryManager, args: List[str]) -> Any:
    """
    SADD key member [member ...]
    반환: 새로 추가된 멤버 수 (integer)
    """
    raise NotImplementedError


def cmd_srem(store: DataStore, expiry: ExpiryManager, args: List[str]) -> Any:
    """
    SREM key member [member ...]
    반환: 삭제된 멤버 수 (integer)
    """
    raise NotImplementedError


def cmd_smembers(store: DataStore, expiry: ExpiryManager, args: List[str]) -> Any:
    """
    SMEMBERS key
    반환: 멤버 배열 (순서 보장 없음)
    """
    raise NotImplementedError


def cmd_sismember(store: DataStore, expiry: ExpiryManager, args: List[str]) -> Any:
    """
    SISMEMBER key member
    반환: 1(존재) 또는 0(없음) (integer)
    """
    raise NotImplementedError


def cmd_scard(store: DataStore, expiry: ExpiryManager, args: List[str]) -> Any:
    """
    SCARD key
    반환: 멤버 수 (integer)
    """
    raise NotImplementedError


def cmd_sinter(store: DataStore, expiry: ExpiryManager, args: List[str]) -> Any:
    """
    SINTER key [key ...]
    교집합을 반환합니다.
    반환: 공통 멤버 배열
    힌트: Python set.intersection() 활용
    """
    raise NotImplementedError


def cmd_sunion(store: DataStore, expiry: ExpiryManager, args: List[str]) -> Any:
    """
    SUNION key [key ...]
    합집합을 반환합니다.
    반환: 모든 멤버 배열 (중복 없음)
    힌트: Python set.union() 활용
    """
    raise NotImplementedError


def cmd_sdiff(store: DataStore, expiry: ExpiryManager, args: List[str]) -> Any:
    """
    SDIFF key [key ...]
    첫 번째 키에서 나머지 키들의 차집합을 반환합니다.
    반환: 차집합 멤버 배열
    힌트: Python set.difference() 활용
    """
    raise NotImplementedError

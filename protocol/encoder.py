"""
RESP 인코더 (팀원 A 담당)

Python 객체를 Redis RESP 프로토콜 바이트로 변환합니다.
각 함수를 구현하세요. 함수 이름과 파라미터는 변경하지 마세요.
"""

from typing import Optional, List, Any


def encode_simple_string(s: str) -> bytes:
    """
    Simple String 인코딩 (+)
    예: "OK" → b"+OK\r\n"
    """
    raise NotImplementedError


def encode_error(msg: str) -> bytes:
    """
    Error 인코딩 (-)
    예: "ERR unknown command" → b"-ERR unknown command\r\n"
    """
    raise NotImplementedError


def encode_integer(n: int) -> bytes:
    """
    Integer 인코딩 (:)
    예: 1000 → b":1000\r\n"
    """
    raise NotImplementedError


def encode_bulk_string(s: Optional[str]) -> bytes:
    """
    Bulk String 인코딩 ($)
    예: "foobar" → b"$6\r\nfoobar\r\n"
    예: None (nil) → b"$-1\r\n"
    """
    raise NotImplementedError


def encode_array(items: List[Any]) -> bytes:
    """
    Array 인코딩 (*)
    예: ["foo", "bar"] → b"*2\r\n$3\r\nfoo\r\n$3\r\nbar\r\n"
    예: [] (빈 배열) → b"*0\r\n"
    예: None (nil 배열) → b"*-1\r\n"

    힌트: items의 각 원소에 대해 타입에 따라 적절한 encode 함수를 재귀 호출하세요.
    - str → encode_bulk_string
    - int → encode_integer
    - None → encode_bulk_string(None)
    - list → encode_array (재귀)
    """
    raise NotImplementedError

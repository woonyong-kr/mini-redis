"""
RESP 인코더

Python 객체를 Redis RESP 프로토콜 바이트로 변환합니다.
서버가 클라이언트에게 응답을 보낼 때 사용합니다.

RESP 타입 요약:
  +  Simple String  →  짧은 성공 메시지 (예: OK, PONG)
  -  Error          →  오류 메시지
  :  Integer        →  정수 숫자
  $  Bulk String    →  일반 문자열 (길이 포함)
  *  Array          →  여러 값의 목록
"""

from typing import Optional, List, Any


# ─────────────────────────────────────────────────────────────────
# 응답 타입 래퍼 클래스
#
# Python의 기본 타입(str, int, list)만으로는 RESP 타입을 구분할 수 없습니다.
# 예를 들어 "OK"가 Simple String(+OK)인지 Bulk String($2\r\nOK)인지
# str 타입만 보고는 알 수 없습니다.
#
# 이 래퍼 클래스들은 str을 상속하므로 문자열처럼 쓸 수 있으면서
# isinstance()로 타입을 구분할 수 있게 해줍니다.
# ─────────────────────────────────────────────────────────────────

class SimpleString(str):
    """
    RESP Simple String 용 래퍼 (+OK\r\n 형태)
    SET, PING 등 단순 성공 응답에 사용합니다.

    예: SimpleString("OK") → b"+OK\r\n"
    """
    pass


class RespError(str):
    """
    RESP Error 용 래퍼 (-ERR ...\r\n 형태)
    명령어 오류, 잘못된 인자 등에 사용합니다.

    예: RespError("ERR unknown command") → b"-ERR unknown command\r\n"
    """
    pass


def encode(value: Any) -> bytes:
    """
    Python 값을 RESP 바이트로 변환하는 통합 인코더.
    server.py에서 dispatch() 결과를 전송 전에 이 함수로 변환합니다.

    타입별 변환 규칙:
      RespError   → -ERR ...\r\n
      SimpleString → +OK\r\n
      int          → :숫자\r\n
      list         → *배열\r\n
      str          → $길이\r\n문자열\r\n  (Bulk String)
      None         → $-1\r\n             (nil)
    """
    if isinstance(value, RespError):
        return encode_error(value)
    if isinstance(value, SimpleString):
        return encode_simple_string(value)
    if isinstance(value, int):
        return encode_integer(value)
    if isinstance(value, list):
        return encode_array(value)
    # str 또는 None → Bulk String
    return encode_bulk_string(value)


def encode_simple_string(s: str) -> bytes:
    """
    Simple String 인코딩
    예: "OK" → b"+OK\r\n"

    주로 SET, PING 같은 명령어의 성공 응답에 사용됩니다.
    """
    # RESP Simple String 형식: + 접두사 + 내용 + \r\n (줄끝 표시)
    # f-string으로 문자열을 조립한 뒤 .encode()로 바이트로 변환
    return f"+{s}\r\n".encode()


def encode_error(msg: str) -> bytes:
    """
    Error 인코딩
    예: "ERR unknown command" → b"-ERR unknown command\r\n"

    명령어가 잘못됐거나 처리 중 오류가 발생했을 때 사용합니다.
    redis-py는 - 로 시작하는 응답을 받으면 예외(Exception)를 발생시킵니다.
    """
    # RESP Error 형식: - 접두사 + 메시지 + \r\n
    return f"-{msg}\r\n".encode()


def encode_integer(n: int) -> bytes:
    """
    Integer 인코딩
    예: 1000 → b":1000\r\n"

    INCR, DEL, LLEN 등 숫자를 반환하는 명령어에 사용됩니다.
    """
    # RESP Integer 형식: : 접두사 + 숫자 + \r\n
    return f":{n}\r\n".encode()


def encode_bulk_string(s: Optional[str]) -> bytes:
    """
    Bulk String 인코딩
    예: "foobar" → b"$6\r\nfoobar\r\n"
    예: None     → b"$-1\r\n"  (nil, 값 없음을 의미)

    GET 같은 명령어의 응답에 사용됩니다.
    Simple String과 달리 길이 정보를 앞에 포함하기 때문에
    바이너리 데이터나 공백이 포함된 문자열도 안전하게 전송할 수 있습니다.
    """
    # s가 None이면 "값 없음(nil)"을 의미하는 특수 형식 반환
    # redis-py는 이 응답을 받으면 None을 반환합니다
    if s is None:
        return b"$-1\r\n"

    # 문자열을 바이트로 변환 (길이 계산을 위해)
    # 한글 등 멀티바이트 문자는 문자 수와 바이트 수가 다르므로 encode() 후 길이를 재야 함
    encoded = s.encode()

    # RESP Bulk String 형식: $ + 바이트 길이 + \r\n + 실제 내용 + \r\n
    # 예) "hello" → $5\r\nhello\r\n
    return f"${len(encoded)}\r\n".encode() + encoded + b"\r\n"


def encode_array(items: List[Any]) -> bytes:
    """
    Array 인코딩
    예: ["foo", "bar"] → b"*2\r\n$3\r\nfoo\r\n$3\r\nbar\r\n"
    예: []             → b"*0\r\n"      (빈 배열)
    예: None           → b"*-1\r\n"    (nil 배열)

    KEYS, LRANGE, SMEMBERS 등 여러 값을 반환하는 명령어에 사용됩니다.
    """
    # items가 None이면 nil 배열 반환
    if items is None:
        return b"*-1\r\n"

    # RESP Array 헤더: * + 원소 개수 + \r\n
    # 예) 원소가 2개면 → *2\r\n
    result = f"*{len(items)}\r\n".encode()

    # 각 원소를 타입에 맞게 인코딩해서 이어붙임
    for item in items:
        if isinstance(item, int):
            # 정수는 Integer 인코딩
            result += encode_integer(item)
        elif isinstance(item, list):
            # 리스트 안에 리스트가 있으면 재귀 호출 (중첩 배열)
            result += encode_array(item)
        else:
            # str 또는 None은 Bulk String 인코딩
            # None이면 encode_bulk_string이 $-1\r\n 반환
            result += encode_bulk_string(item)

    return result

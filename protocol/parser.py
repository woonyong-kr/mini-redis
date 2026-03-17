"""
RESP 파서 (팀원 A 담당)

클라이언트가 보낸 RESP 바이트 스트림을 Python 리스트로 파싱합니다.
각 함수를 구현하세요. 함수 이름과 파라미터는 변경하지 마세요.
"""

from typing import Optional, Tuple, List


def parse(data: bytes) -> Tuple[Optional[List[str]], int]:
    """
    RESP 바이트를 파싱하여 명령어 리스트를 반환합니다.

    반환값: (parsed_command, bytes_consumed)
      - parsed_command: ["SET", "foo", "bar"] 형태의 리스트
                        파싱 불완전하면 None
      - bytes_consumed: 파싱에 사용된 바이트 수 (0이면 데이터 부족)

    예시:
      parse(b"*3\r\n$3\r\nSET\r\n$3\r\nfoo\r\n$3\r\nbar\r\n")
      → (["SET", "foo", "bar"], 34)

    힌트:
      1. data[0]으로 첫 바이트를 확인해 타입 판별
      2. b'*' → Array (클라이언트 명령은 항상 Array)
      3. \r\n 위치를 찾아 길이/내용 파싱
      4. 데이터가 불완전하면 (None, 0) 반환
    """
    raise NotImplementedError


def _parse_array(data: bytes, pos: int) -> Tuple[Optional[List], int]:
    """
    Array 타입 파싱 내부 함수.
    pos: data에서 '*' 다음 위치부터 시작

    반환값: (parsed_list, new_pos)
    """
    raise NotImplementedError


def _parse_bulk_string(data: bytes, pos: int) -> Tuple[Optional[str], int]:
    """
    Bulk String 타입 파싱 내부 함수.
    pos: data에서 '$' 다음 위치부터 시작

    반환값: (string_value, new_pos)
    """
    raise NotImplementedError

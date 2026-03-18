"""
RESP 파서

클라이언트(redis-cli, redis-py 등)가 보낸 RESP 바이트 스트림을
Python 리스트로 변환합니다.

예시 흐름:
  클라이언트가 보내는 바이트:
    b"*3\r\n$3\r\nSET\r\n$3\r\nfoo\r\n$3\r\nbar\r\n"

  파싱 결과:
    (["SET", "foo", "bar"], 34)
     ↑ 명령어 리스트          ↑ 소비한 바이트 수

왜 소비한 바이트 수를 반환하는가?
  클라이언트가 파이프라인(명령어 여러 개를 한 번에 전송)을 사용하면
  버퍼에 명령어가 여러 개 붙어 들어올 수 있습니다.
  server.py는 이 숫자만큼 버퍼를 잘라내고, 남은 부분을 다시 파싱합니다.
"""

from typing import Optional, Tuple, List


def parse(data: bytes) -> Tuple[Optional[List[str]], int]:
    """
    RESP 바이트의 진입점 파서.

    반환값: (parsed_command, bytes_consumed)
      - parsed_command : ["SET", "foo", "bar"] 형태의 리스트
                         데이터가 불완전하면 None
      - bytes_consumed : 이번 파싱에 사용한 바이트 수
                         데이터가 불완전하면 0
    """
    # 데이터가 아예 비어있으면 처리할 게 없으므로 바로 반환
    if not data:
        return None, 0

    # 첫 번째 바이트로 RESP 타입을 판별합니다
    # 클라이언트가 보내는 명령어는 항상 Array(*) 형태입니다
    # 예) SET foo bar → *3\r\n$3\r\nSET\r\n...
    first_byte = data[0:1]  # b'*', b'+', b'-', b':' 또는 b'$' 중 하나

    if first_byte == b"*":
        # Array 타입: 클라이언트 명령어의 표준 형식
        # 1을 넘기는 이유: '*' 자체는 이미 읽었으니 그 다음 위치부터 파싱
        result, pos = _parse_array(data, 1)
        return result, pos

    # 현재 구현에서는 Array만 처리합니다
    # (클라이언트 → 서버 방향은 항상 Array이므로 충분합니다)
    return None, 0


def _parse_array(data: bytes, pos: int) -> Tuple[Optional[List], int]:
    """
    Array 타입 파싱 내부 함수.

    Array 형식: *{원소 개수}\r\n{원소1}{원소2}...
    예) *3\r\n$3\r\nSET\r\n$3\r\nfoo\r\n$3\r\nbar\r\n
         ↑ pos=1 에서 시작 ('*' 다음)

    반환값: (파싱된 리스트, 다음 파싱 위치)
    """
    # \r\n 위치를 찾아 원소 개수 줄을 읽습니다
    # 예) b"3\r\n$3\r\nSET..." 에서 \r\n 위치를 찾으면 index=1
    crlf = data.find(b"\r\n", pos)

    # \r\n이 없다면 데이터가 아직 덜 도착한 것 → (None, 0) 반환
    if crlf == -1:
        return None, 0

    # pos부터 \r\n 직전까지가 원소 개수 문자열입니다
    # 예) b"3" → int("3") → 3
    count = int(data[pos:crlf])

    # 다음 파싱 위치는 \r\n 이후 (+ 2는 \r\n 두 글자)
    pos = crlf + 2

    # 원소들을 담을 결과 리스트
    result = []

    # count 만큼 반복해서 원소를 하나씩 파싱합니다
    for _ in range(count):
        # 데이터가 부족하면 아직 받지 못한 것
        if pos >= len(data):
            return None, 0

        # 현재 위치의 바이트로 원소 타입 판별
        element_type = data[pos:pos + 1]

        if element_type == b"$":
            # Bulk String 타입 ($): 일반 문자열
            # '$' 다음 위치(pos+1)부터 파싱 시작
            value, pos = _parse_bulk_string(data, pos + 1)

            # 파싱 실패 (데이터 부족)
            if value is None:
                return None, 0

            result.append(value)

        else:
            # 예상하지 못한 타입 → 파싱 불가
            return None, 0

    # 모든 원소 파싱 완료
    # result: 파싱된 명령어 리스트
    # pos: 지금까지 소비한 총 바이트 수 (다음 명령어의 시작 위치)
    return result, pos


def _parse_bulk_string(data: bytes, pos: int) -> Tuple[Optional[str], int]:
    """
    Bulk String 타입 파싱 내부 함수.

    Bulk String 형식: ${길이}\r\n{내용}\r\n
    예) $3\r\nSET\r\n
         ↑ pos=1 에서 시작 ('$' 다음)

    반환값: (문자열 값, 다음 파싱 위치)
    """
    # \r\n 위치를 찾아 길이 줄을 읽습니다
    crlf = data.find(b"\r\n", pos)

    # \r\n이 없으면 데이터 부족
    if crlf == -1:
        return None, 0

    # pos부터 \r\n 직전까지가 바이트 길이 문자열입니다
    # 예) b"3" → int("3") → 3
    length = int(data[pos:crlf])

    # 길이가 -1이면 nil (값 없음)
    # 서버→클라이언트 응답에서 사용하지만 완전성을 위해 처리
    if length == -1:
        return None, crlf + 2

    # 실제 문자열이 시작하는 위치: \r\n 이후
    start = crlf + 2

    # 문자열이 끝나는 위치: 시작 위치 + 길이
    end = start + length

    # 아직 해당 바이트까지 데이터가 도착하지 않은 경우
    if end + 2 > len(data):  # +2는 내용 뒤의 \r\n
        return None, 0

    # start부터 end까지 슬라이싱해서 실제 문자열 추출
    # .decode()로 bytes → str 변환
    value = data[start:end].decode()

    # 다음 파싱 위치: 내용 끝 + \r\n (2바이트)
    return value, end + 2

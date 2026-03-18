"""RESP request parser used by the TCP server.

The parser only accepts the subset the server needs from clients:
RESP arrays made of bulk strings. It returns both the parsed command and the
number of consumed bytes so the connection loop can keep handling pipelines.
"""

from __future__ import annotations

from typing import List, Optional, Tuple


RESP_ENCODING = "utf-8"
RESP_ERRORS = "surrogateescape"


def parse(data: bytes) -> Tuple[Optional[List[str]], int]:
    if not data:
        return None, 0

    if data[0:1] != b"*":
        return None, 0

    result, position = _parse_array(data, 1)
    return result, position


def _parse_array(data: bytes, pos: int) -> Tuple[Optional[List[str]], int]:
    crlf = data.find(b"\r\n", pos)
    if crlf == -1:
        return None, 0

    count = int(data[pos:crlf])
    pos = crlf + 2
    result: List[str] = []

    for _ in range(count):
        if pos >= len(data):
            return None, 0

        if data[pos:pos + 1] != b"$":
            return None, 0

        value, pos = _parse_bulk_string(data, pos + 1)
        if value is None:
            return None, 0
        result.append(value)

    return result, pos


def _parse_bulk_string(data: bytes, pos: int) -> Tuple[Optional[str], int]:
    crlf = data.find(b"\r\n", pos)
    if crlf == -1:
        return None, 0

    length = int(data[pos:crlf])
    if length == -1:
        return None, crlf + 2

    start = crlf + 2
    end = start + length
    if end + 2 > len(data):
        return None, 0

    value = data[start:end].decode(RESP_ENCODING, errors=RESP_ERRORS)
    return value, end + 2

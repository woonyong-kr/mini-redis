"""RESP response encoder.

Command handlers return plain Python values and a few lightweight wrappers.
This module translates those values into RESP bytes and caches the hottest
simple replies to keep the write path small.
"""

from __future__ import annotations

from typing import Any, List, Optional, Union


RESP_ENCODING = "utf-8"
RESP_ERRORS = "surrogateescape"

RESP_OK = b"+OK\r\n"
RESP_PONG = b"+PONG\r\n"
RESP_NULL_BULK = b"$-1\r\n"
RESP_NULL_ARRAY = b"*-1\r\n"


class SimpleString(str):
    """Marks a value that should be encoded as a RESP simple string."""


class RespError(str):
    """Marks a value that should be encoded as a RESP error."""


def encode(value: Any) -> bytes:
    if isinstance(value, RespError):
        return encode_error(value)
    if isinstance(value, SimpleString):
        return encode_simple_string(value)
    if isinstance(value, int):
        return encode_integer(value)
    if isinstance(value, list):
        return encode_array(value)
    return encode_bulk_string(value)


def encode_simple_string(value: str) -> bytes:
    if value == "OK":
        return RESP_OK
    if value == "PONG":
        return RESP_PONG
    return f"+{value}\r\n".encode(RESP_ENCODING, errors=RESP_ERRORS)


def encode_error(message: str) -> bytes:
    return f"-{message}\r\n".encode(RESP_ENCODING, errors=RESP_ERRORS)


def encode_integer(value: int) -> bytes:
    return f":{value}\r\n".encode(RESP_ENCODING, errors=RESP_ERRORS)


def encode_bulk_string(value: Optional[Union[str, bytes]]) -> bytes:
    if value is None:
        return RESP_NULL_BULK

    if isinstance(value, bytes):
        encoded = value
    else:
        encoded = value.encode(RESP_ENCODING, errors=RESP_ERRORS)

    return f"${len(encoded)}\r\n".encode(RESP_ENCODING, errors=RESP_ERRORS) + encoded + b"\r\n"


def encode_array(items: List[Any]) -> bytes:
    if items is None:
        return RESP_NULL_ARRAY

    result = f"*{len(items)}\r\n".encode(RESP_ENCODING, errors=RESP_ERRORS)
    for item in items:
        if isinstance(item, int):
            result += encode_integer(item)
        elif isinstance(item, list):
            result += encode_array(item)
        else:
            result += encode_bulk_string(item)
    return result

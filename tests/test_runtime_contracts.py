import asyncio

import pytest

from protocol.encoder import encode_bulk_string
from protocol.parser import parse
from server import Server
from store.datastore import DataStore
from store.redis_object import make_string


def encode_command(*parts) -> bytes:
    encoded_parts = []
    for part in parts:
        if isinstance(part, str):
            raw = part.encode("utf-8")
        else:
            raw = part
        encoded_parts.append(f"${len(raw)}\r\n".encode() + raw + b"\r\n")
    return f"*{len(encoded_parts)}\r\n".encode() + b"".join(encoded_parts)


def test_protocol_round_trip_preserves_invalid_utf8_bytes():
    payload = b"\xff\xfehello\x80"
    command, consumed = parse(encode_command("SET", "bin", payload))

    assert consumed > 0
    assert command is not None
    assert encode_bulk_string(command[2]) == f"${len(payload)}\r\n".encode() + payload + b"\r\n"


def test_datastore_delete_hooks_run_on_delete_and_flush():
    store = DataStore()
    deleted = []
    store.register_delete_hook(deleted.append)

    store.set("alpha", make_string("1"))
    store.set("beta", make_string("2"))

    assert store.delete("alpha") == 1
    store.flush()

    assert deleted == ["alpha", "beta"]


@pytest.mark.asyncio
async def test_subscribe_mode_returns_to_general_mode_after_unsubscribe():
    redis_server = Server()
    tcp_server = await asyncio.start_server(redis_server.handle_client, "127.0.0.1", 0)
    host, port = tcp_server.sockets[0].getsockname()[:2]

    reader, writer = await asyncio.open_connection(host, port)

    subscribe_reply = b"*3\r\n$9\r\nsubscribe\r\n$4\r\nnews\r\n:1\r\n"
    unsubscribe_reply = b"*3\r\n$11\r\nunsubscribe\r\n$4\r\nnews\r\n:0\r\n"

    writer.write(encode_command("SUBSCRIBE", "news"))
    await writer.drain()
    assert await asyncio.wait_for(reader.readexactly(len(subscribe_reply)), timeout=1) == subscribe_reply

    writer.write(encode_command("UNSUBSCRIBE", "news") + encode_command("PING"))
    await writer.drain()
    assert await asyncio.wait_for(reader.readexactly(len(unsubscribe_reply)), timeout=1) == unsubscribe_reply
    assert await asyncio.wait_for(reader.readexactly(len(b"+PONG\r\n")), timeout=1) == b"+PONG\r\n"

    writer.close()
    await writer.wait_closed()

    tcp_server.close()
    await tcp_server.wait_closed()

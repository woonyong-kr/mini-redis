"""
mini-redis 서버 진입점

asyncio 기반 TCP 서버로, Redis 클라이언트(redis-cli, redis-py 등)와
RESP 프로토콜로 통신합니다.

실행 방법:
  python server.py
  python server.py --host 0.0.0.0 --port 6380

테스트 방법:
  redis-cli -p 6379 ping
  redis-cli -p 6379 set foo bar
  redis-cli -p 6379 get foo
"""

import asyncio
import argparse
import logging
import os
import uvloop

asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

from store.datastore import DataStore
from store.expiry import ExpiryManager
from store.pubsub import PubSubManager
from protocol.parser import parse
from protocol.encoder import encode, RespError
from commands.dispatcher import dispatch
from commands.pubsub_cmds import cmd_subscribe, cmd_unsubscribe


def _env_int(name: str, default: int, *, min_value: int = 1) -> int:
    raw = os.getenv(name)
    if raw in (None, ""):
        return default

    value = int(raw)
    if value < min_value:
        raise ValueError(f"{name} must be >= {min_value}, got {value}")
    return value


def _env_float(name: str, default: float, *, min_value: float = 0.0) -> float:
    raw = os.getenv(name)
    if raw in (None, ""):
        return default

    value = float(raw)
    if value < min_value:
        raise ValueError(f"{name} must be >= {min_value}, got {value}")
    return value


DEFAULT_HOST = os.getenv("MINI_REDIS_HOST", "127.0.0.1")
DEFAULT_PORT = _env_int("MINI_REDIS_PORT", 6379)
DEFAULT_READ_CHUNK = _env_int("MINI_REDIS_READ_CHUNK", 4096)
DEFAULT_EXPIRY_LOOP_INTERVAL = (
    _env_float("MINI_REDIS_EXPIRY_LOOP_INTERVAL_MS", 100.0, min_value=1.0) / 1000.0
)
DEFAULT_LOG_LEVEL = os.getenv("MINI_REDIS_LOG_LEVEL", "INFO").upper()

logging.basicConfig(
    level=getattr(logging, DEFAULT_LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


class Server:

    def __init__(
        self,
        *,
        read_chunk: int = DEFAULT_READ_CHUNK,
        expiry_interval_seconds: float = DEFAULT_EXPIRY_LOOP_INTERVAL,
    ):
        # 서버 전체에서 공유하는 인메모리 스토어와 TTL 관리자
        self.store = DataStore()
        self.expiry = ExpiryManager(self.store, interval_seconds=expiry_interval_seconds)
        # Pub/Sub 채널 관리자 (DataStore와 독립적으로 존재)
        self.pubsub = PubSubManager()
        self.read_chunk = read_chunk

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """
        클라이언트 연결 핸들러.
        클라이언트가 접속할 때마다 이 코루틴이 하나씩 실행됩니다.

        두 가지 모드:
          1. 일반 모드: 요청 → 응답 (기존 방식)
          2. 구독 모드: SUBSCRIBE 이후 진입, 서버가 먼저 push 가능
        """
        addr = writer.get_extra_info("peername")
        buffer = b""

        try:
            while True:
                # 클라이언트로부터 설정된 청크 크기만큼 읽음
                chunk = await reader.read(self.read_chunk)
                if not chunk:
                    break  # 빈 데이터 = 클라이언트가 연결을 끊은 것

                buffer += chunk

                # 버퍼에서 완전한 명령어를 하나씩 꺼내 처리 (파이프라인 지원)
                while buffer:
                    command, consumed = parse(buffer)
                    if command is None:
                        break  # 데이터가 불완전 → 다음 read()에서 더 받을 때까지 대기

                    buffer = buffer[consumed:]  # 파싱한 만큼 버퍼에서 제거

                    cmd_name = command[0].upper() if command else ""

                    # ── Pub/Sub 전용 명령어 처리 ──────────────────────────────
                    if cmd_name == "SUBSCRIBE":
                        channels = command[1:]
                        if not channels:
                            writer.write(encode(RespError("ERR wrong number of arguments for 'subscribe' command")))
                            await writer.drain()
                            continue
                        await cmd_subscribe(self.pubsub, writer, channels)
                        # 구독 모드 전환: 이 연결은 이제 push 수신 전용
                        should_close, buffer = await self._subscribe_loop(reader, writer, buffer)
                        if should_close:
                            return
                        continue

                    elif cmd_name == "PUBLISH":
                        # PUBLISH는 구독 모드가 아닌 일반 클라이언트가 사용
                        if len(command) != 3:
                            writer.write(encode(RespError("ERR wrong number of arguments for 'publish' command")))
                        else:
                            from commands.pubsub_cmds import cmd_publish
                            count = await cmd_publish(self.pubsub, command[1], command[2])
                            writer.write(encode(count))

                    # ── 일반 명령어 처리 ─────────────────────────────────────
                    else:
                        result = dispatch(command, self.store, self.expiry)
                        writer.write(encode(result))

                await writer.drain()  # 응답을 실제로 전송

        except ConnectionResetError:
            pass  # 클라이언트가 갑자기 끊어도 서버는 계속 동작
        except Exception as e:
            logger.error(f"Error handling client {addr}: {e}")
            try:
                writer.write(encode(RespError(f"ERR server error: {str(e)}")))
                await writer.drain()
            except Exception:
                pass
        finally:
            self.pubsub.unsubscribe_all(writer)  # 연결 종료 시 구독 정리
            writer.close()  # 어떤 경우든 연결은 반드시 닫음

    async def _subscribe_loop(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        buffer: bytes = b"",
    ) -> tuple[bool, bytes]:
        """
        구독 모드 전용 루프.

        SUBSCRIBE 이후 이 연결은 구독 모드가 됩니다.
        구독 모드에서는 SUBSCRIBE, UNSUBSCRIBE, PING, QUIT만 허용됩니다.
        (실제 Redis 동일한 동작)

        발행된 메시지는 PubSubManager.publish()에서 writer에 직접 씁니다.
        이 루프는 클라이언트가 UNSUBSCRIBE로 모두 해제하거나
        연결을 끊을 때까지 실행됩니다.
        """
        while True:
            while buffer:
                command, consumed = parse(buffer)
                if command is None:
                    break
                buffer = buffer[consumed:]

                cmd_name = command[0].upper() if command else ""

                if cmd_name == "SUBSCRIBE":
                    # 구독 모드 안에서 추가 채널 구독
                    await cmd_subscribe(self.pubsub, writer, command[1:])

                elif cmd_name == "UNSUBSCRIBE":
                    # 구독 해제
                    await cmd_unsubscribe(self.pubsub, writer, command[1:])
                    # 모든 채널 해제되면 일반 모드로 복귀 가능 (연결은 유지)
                    if not self.pubsub.get_subscribed_channels(writer):
                        return False, buffer

                elif cmd_name == "PING":
                    # 구독 모드의 PING은 *3 배열 형태로 응답
                    msg = command[1] if len(command) > 1 else ""
                    from store.pubsub import _encode_bulk
                    pong_payload = b"*3\r\n" + _encode_bulk("pong") + _encode_bulk("") + _encode_bulk(msg)
                    writer.write(pong_payload)
                    await writer.drain()

                elif cmd_name == "QUIT":
                    writer.write(encode("OK"))
                    await writer.drain()
                    return True, b""

                else:
                    # 구독 모드에서 허용되지 않는 명령어
                    writer.write(encode(RespError(
                        f"ERR Command '{cmd_name}' not allowed in subscribe mode"
                    )))
                    await writer.drain()

            try:
                chunk = await reader.read(self.read_chunk)
                if not chunk:
                    return True, b""
            except (ConnectionResetError, OSError):
                return True, b""

            buffer += chunk

    async def start(self, host: str = "127.0.0.1", port: int = 6379):
        """서버 시작"""
        # 만료 키 청소 루프를 백그라운드에서 실행
        asyncio.create_task(self.expiry.active_expiry_loop())

        server = await asyncio.start_server(self.handle_client, host, port)

        logger.info(f"mini-redis server started on {host}:{port}")

        async with server:
            await server.serve_forever()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="mini-redis server")
    parser.add_argument("--host", default=DEFAULT_HOST, help="Bind host")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Bind port")
    args = parser.parse_args()

    server = Server()
    asyncio.run(server.start(host=args.host, port=args.port))

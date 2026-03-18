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
import uvloop

asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

from store.datastore import DataStore
from store.expiry import ExpiryManager
from protocol.parser import parse
from protocol.encoder import encode, RespError
from commands.dispatcher import dispatch

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


class RedisServer:

    def __init__(self):
        # 서버 전체에서 공유하는 인메모리 스토어와 TTL 관리자
        self.store = DataStore()
        self.expiry = ExpiryManager(self.store)

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """
        클라이언트 연결 핸들러.
        클라이언트가 접속할 때마다 이 코루틴이 하나씩 실행됩니다.
        """
        addr = writer.get_extra_info("peername")
        buffer = b""

        try:
            while True:
                # 클라이언트로부터 최대 4096바이트씩 읽음
                chunk = await reader.read(4096)
                if not chunk:
                    break  # 빈 데이터 = 클라이언트가 연결을 끊은 것

                buffer += chunk

                # 버퍼에서 완전한 명령어를 하나씩 꺼내 처리 (파이프라인 지원)
                while buffer:
                    command, consumed = parse(buffer)
                    if command is None:
                        break  # 데이터가 불완전 → 다음 read()에서 더 받을 때까지 대기

                    buffer = buffer[consumed:]  # 파싱한 만큼 버퍼에서 제거

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
            writer.close()  # 어떤 경우든 연결은 반드시 닫음

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
    parser.add_argument("--host", default="127.0.0.1", help="Bind host")
    parser.add_argument("--port", type=int, default=6379, help="Bind port")
    args = parser.parse_args()

    redis_server = RedisServer()
    asyncio.run(redis_server.start(host=args.host, port=args.port))

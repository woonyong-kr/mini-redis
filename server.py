"""
mini-redis 서버 진입점 (리더 담당)

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

try:
    import uvloop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    logging.info("uvloop enabled")
except ImportError:
    logging.info("uvloop not found, using default asyncio event loop")

from store.datastore import DataStore
from store.expiry import ExpiryManager
from protocol.parser import parse
from protocol.encoder import encode_error
from commands.dispatcher import dispatch

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

# 전역 스토어 (단일 인스턴스)
store = DataStore()
expiry = ExpiryManager(store)


async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    """
    클라이언트 연결 핸들러.
    각 클라이언트마다 이 코루틴이 실행됩니다.
    """
    addr = writer.get_extra_info("peername")
    logger.info(f"Client connected: {addr}")

    buffer = b""

    try:
        while True:
            # 데이터 읽기
            chunk = await reader.read(4096)
            if not chunk:
                break  # 클라이언트 연결 종료

            buffer += chunk

            # 버퍼에서 완전한 명령어 처리 (파이프라인 지원)
            while buffer:
                command, consumed = parse(buffer)
                if command is None:
                    break  # 아직 데이터가 부족함 (더 읽어야 함)

                buffer = buffer[consumed:]

                # 명령어 실행
                response = dispatch(command, store, expiry)
                writer.write(response)

            await writer.drain()

    except ConnectionResetError:
        pass
    except Exception as e:
        logger.error(f"Error handling client {addr}: {e}")
        try:
            writer.write(encode_error(f"ERR server error: {str(e)}"))
            await writer.drain()
        except Exception:
            pass
    finally:
        writer.close()
        logger.info(f"Client disconnected: {addr}")


async def main(host: str = "127.0.0.1", port: int = 6379):
    """서버 시작"""
    # 백그라운드 만료 루프 시작
    asyncio.create_task(expiry.active_expiry_loop())

    server = await asyncio.start_server(handle_client, host, port)

    logger.info(f"mini-redis server started on {host}:{port}")
    logger.info("Connect with: redis-cli -p %d", port)

    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="mini-redis server")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host")
    parser.add_argument("--port", type=int, default=6379, help="Bind port")
    args = parser.parse_args()

    asyncio.run(main(host=args.host, port=args.port))

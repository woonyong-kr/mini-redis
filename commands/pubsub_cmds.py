"""
Pub/Sub 명령어 핸들러

SUBSCRIBE / UNSUBSCRIBE / PUBLISH / PUBSUB 명령어를 처리합니다.

⚠️ 일반 명령어와 다른 점:
  - SUBSCRIBE는 응답을 직접 writer에 써야 합니다. (서버가 push하는 방향)
  - SUBSCRIBE 이후 연결은 "구독 모드"로 전환됩니다.
    구독 모드에서는 SUBSCRIBE, UNSUBSCRIBE, PING, QUIT만 허용됩니다.
  - 이 파일의 함수들은 server.py의 구독 루프에서 직접 호출됩니다.
"""

import asyncio
from typing import List, Any

from store.pubsub import PubSubManager, encode_subscribe_reply
from protocol.encoder import RespError, encode


async def cmd_subscribe(
    pubsub: PubSubManager,
    writer: asyncio.StreamWriter,
    channels: List[str],
) -> None:
    """
    SUBSCRIBE channel [channel ...]

    각 채널을 구독하고, 채널마다 확인 응답을 즉시 전송합니다.
    응답 형식: *3\r\n$9\r\nsubscribe\r\n${ch_len}\r\n{channel}\r\n:{count}\r\n
    """
    for channel in channels:
        count = pubsub.subscribe(channel, writer)
        reply = encode_subscribe_reply("subscribe", channel, count)
        writer.write(reply)
    await writer.drain()


async def cmd_unsubscribe(
    pubsub: PubSubManager,
    writer: asyncio.StreamWriter,
    channels: List[str],
) -> None:
    """
    UNSUBSCRIBE [channel ...]

    채널 목록이 비어있으면 모든 채널을 해제합니다.
    """
    if not channels:
        # 인자 없으면 모든 채널 해제
        channels = pubsub.get_subscribed_channels(writer)

    for channel in channels:
        count = pubsub.unsubscribe(channel, writer)
        reply = encode_subscribe_reply("unsubscribe", channel, count)
        writer.write(reply)
    await writer.drain()


async def cmd_publish(
    pubsub: PubSubManager,
    channel: str,
    message: str,
) -> int:
    """
    PUBLISH channel message

    채널에 메시지를 발행하고, 수신한 구독자 수를 반환합니다.
    반환값은 dispatcher를 통해 일반 Integer 응답으로 인코딩됩니다.
    """
    return await pubsub.publish(channel, message)

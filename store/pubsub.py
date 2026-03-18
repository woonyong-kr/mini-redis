"""
Pub/Sub 채널 관리자

Redis Pub/Sub의 핵심 구조:
  - 채널(channel): 메시지가 흐르는 이름 붙은 통로
  - 구독자(subscriber): asyncio.StreamWriter - 열려있는 TCP 연결
  - 발행자(publisher): PUBLISH 명령을 보낸 어떤 클라이언트든

내부 구조:
  _channels: dict[channel_name, set[asyncio.StreamWriter]]
  예: {"news": {writer1, writer2}, "sports": {writer3}}

실제 Redis도 동일한 방식:
  server.pubsub_channels → dict (channel → list of clients)
"""

import asyncio
from collections import defaultdict
from typing import Dict, Set

RESP_ENCODING = "utf-8"
RESP_ERRORS = "surrogateescape"


class PubSubManager:
    """
    채널 ↔ 구독자(Writer) 매핑을 관리하는 싱글턴 레이어.

    DataStore와 독립적으로 존재합니다.
    Pub/Sub 메시지는 저장되지 않고 즉시 전달(fire-and-forget)됩니다.
    """

    def __init__(self):
        # channel_name → 구독 중인 StreamWriter들의 집합
        self._channels: Dict[str, Set[asyncio.StreamWriter]] = defaultdict(set)

    # ─────────────────────────────────────────
    # 구독 관리
    # ─────────────────────────────────────────

    def subscribe(self, channel: str, writer: asyncio.StreamWriter) -> int:
        """
        writer(클라이언트 연결)를 channel에 구독 등록합니다.
        반환: 이 writer가 현재 구독 중인 채널 수
        """
        self._channels[channel].add(writer)
        return self._subscriber_count(writer)

    def unsubscribe(self, channel: str, writer: asyncio.StreamWriter) -> int:
        """
        writer를 channel에서 해제합니다.
        반환: 이 writer가 현재 구독 중인 채널 수
        """
        self._channels[channel].discard(writer)
        # 채널에 구독자가 없으면 채널 자체를 제거 (메모리 정리)
        if not self._channels[channel]:
            del self._channels[channel]
        return self._subscriber_count(writer)

    def unsubscribe_all(self, writer: asyncio.StreamWriter) -> None:
        """
        연결이 끊어질 때 해당 writer의 모든 구독을 해제합니다.
        """
        channels_to_clean = [
            ch for ch, writers in list(self._channels.items())
            if writer in writers
        ]
        for ch in channels_to_clean:
            self.unsubscribe(ch, writer)

    def get_subscribed_channels(self, writer: asyncio.StreamWriter) -> list:
        """writer가 구독 중인 채널 목록을 반환합니다."""
        return [ch for ch, writers in self._channels.items() if writer in writers]

    # ─────────────────────────────────────────
    # 발행
    # ─────────────────────────────────────────

    async def publish(self, channel: str, message: str) -> int:
        """
        channel의 모든 구독자에게 message를 비동기 전송합니다.
        반환: 실제로 메시지를 받은 구독자 수

        RESP 메시지 형식 (3-element Array):
          *3\r\n
          $7\r\nmessage\r\n     ← 항상 "message" 문자열
          ${len}\r\n{channel}\r\n ← 채널 이름
          ${len}\r\n{message}\r\n ← 실제 메시지
        """
        subscribers = list(self._channels.get(channel, set()))
        if not subscribers:
            return 0

        # RESP 포맷으로 메시지 인코딩
        payload = _encode_pubsub_message("message", channel, message)

        # 모든 구독자에게 동시에 전송
        count = 0
        for writer in subscribers:
            try:
                writer.write(payload)
                await writer.drain()
                count += 1
            except (ConnectionResetError, BrokenPipeError, OSError):
                # 이미 끊어진 연결은 조용히 정리
                self.unsubscribe_all(writer)

        return count

    # ─────────────────────────────────────────
    # 내부 헬퍼
    # ─────────────────────────────────────────

    def _subscriber_count(self, writer: asyncio.StreamWriter) -> int:
        """특정 writer가 구독 중인 채널 수를 셉니다."""
        return sum(1 for writers in self._channels.values() if writer in writers)

    def channel_count(self) -> int:
        """현재 활성 채널 수를 반환합니다. (PUBSUB CHANNELS 용)"""
        return len(self._channels)

    def numsub(self, *channels: str) -> dict:
        """각 채널의 구독자 수를 반환합니다. (PUBSUB NUMSUB 용)"""
        return {ch: len(self._channels.get(ch, set())) for ch in channels}


# ─────────────────────────────────────────
# RESP 메시지 인코딩 헬퍼
# ─────────────────────────────────────────

def _encode_bulk(s: str) -> bytes:
    """문자열을 RESP Bulk String으로 인코딩합니다."""
    encoded = s.encode(RESP_ENCODING, errors=RESP_ERRORS)
    return f"${len(encoded)}\r\n".encode(RESP_ENCODING, errors=RESP_ERRORS) + encoded + b"\r\n"


def encode_subscribe_reply(kind: str, channel: str, count: int) -> bytes:
    """
    SUBSCRIBE / UNSUBSCRIBE 응답 인코딩.

    형식:
      *3\r\n
      $9\r\nsubscribe\r\n   ← "subscribe" or "unsubscribe"
      ${len}\r\n{channel}\r\n
      :{count}\r\n          ← 현재 구독 채널 수
    """
    return (
        b"*3\r\n"
        + _encode_bulk(kind)
        + _encode_bulk(channel)
        + f":{count}\r\n".encode(RESP_ENCODING, errors=RESP_ERRORS)
    )


def _encode_pubsub_message(kind: str, channel: str, message: str) -> bytes:
    """
    PUBLISH로 전달되는 메시지 인코딩.

    형식:
      *3\r\n
      $7\r\nmessage\r\n
      ${len}\r\n{channel}\r\n
      ${len}\r\n{message}\r\n
    """
    return (
        b"*3\r\n"
        + _encode_bulk(kind)
        + _encode_bulk(channel)
        + _encode_bulk(message)
    )

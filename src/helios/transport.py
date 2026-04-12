from __future__ import annotations

import asyncio
import contextlib
import struct

from generated.helios.transport import TransportMessage

from helios.errors import ConnectionError as HeliosConnectionError


class HeliosTransport:
    """Async framed transport for talking to the Helios core."""

    PROTOCOL_VERSION = 1
    MAX_FRAME_BYTES = 16 * 1024 * 1024  # 16MB

    def __init__(self, core_address: str, core_port: int) -> None:
        self._core_address = core_address
        self._core_port = core_port
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None

    @property
    def is_connected(self) -> bool:
        return self._writer is not None

    async def connect(self) -> None:
        if self._writer is not None:
            raise HeliosConnectionError("already connected")
        try:
            self._reader, self._writer = await asyncio.open_connection(
                self._core_address,
                self._core_port,
            )
        except OSError as e:
            raise HeliosConnectionError(str(e)) from e

    async def reset(self) -> None:
        writer = self._writer
        self._reader = None
        self._writer = None
        if writer is not None:
            writer.close()
            with contextlib.suppress(Exception):
                await writer.wait_closed()

    async def write_payload(self, message: TransportMessage) -> None:
        payload = message.SerializeToString()
        if len(payload) > self.MAX_FRAME_BYTES:
            raise HeliosConnectionError("message too large to send")
        if self._writer is None:
            raise HeliosConnectionError("not connected")
        self._writer.write(struct.pack("!I", len(payload)) + payload)
        await self._writer.drain()

    async def read_payload(self) -> TransportMessage:
        if self._reader is None:
            raise HeliosConnectionError("not connected")
        header = await self._reader.readexactly(4)
        (size,) = struct.unpack_from("!I", header, 0)
        if size > self.MAX_FRAME_BYTES:
            raise HeliosConnectionError(f"frame too large: {size} bytes")
        if size == 0:
            raise HeliosConnectionError("empty frame")
        raw = await self._reader.readexactly(size)
        return TransportMessage.parse(raw)

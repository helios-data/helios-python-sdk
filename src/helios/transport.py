from __future__ import annotations

import asyncio
import contextlib
import struct
from typing import Callable

from .generated.helios.transport import TransportMessage

from helios.errors import ConnectionError as HeliosConnectionError


import logging

logger = logging.getLogger(__name__)

class HeliosTransport:
    """Async framed transport for talking to the Helios core."""

    PROTOCOL_VERSION = 1
    MAX_FRAME_BYTES = 16 * 1024 * 1024  # 16MB

    def __init__(
        self,
        core_address: str,
        core_port: int,
        *,
        pending_requests: dict[str, asyncio.Future] | None = None,
    ) -> None:
        self._core_address = core_address
        self._core_port = core_port
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._reader_task: asyncio.Task[None] | None = None
        self._writer_task: asyncio.Task[None] | None = None
        self._write_queue: asyncio.Queue[TransportMessage] = asyncio.Queue()
        self._message_callbacks: dict[str, Callable[[TransportMessage], None]] = {}

    @property
    def is_connected(self) -> bool:
        return self._writer is not None

    async def connect(self) -> None:
        if self._writer is not None:
            raise HeliosConnectionError("Cannot connect to Helios: Already connected")
        try:
            self._reader, self._writer = await asyncio.open_connection(
                self._core_address,
                self._core_port,
            )
        except OSError as e:
            raise HeliosConnectionError(f"Cannot connect to Helios: {str(e)}") from e

    async def start_tasks(self) -> None:
        """Starts the background tasks for the transport layer."""
        self._reader_task = asyncio.create_task(self._run_reader_task())
        self._writer_task = asyncio.create_task(self._run_writer_task())

    async def enqueue_outgoing(self, message: TransportMessage) -> None:
        """Enqueues an outgoing message to be written to the transport layer."""
        await self._write_queue.put(message)

    async def _run_reader_task(self) -> None:
        while self._reader is not None:
            try:
                message = await self.read_payload()
                for callback_name, callback in self._message_callbacks.items():
                    try:
                        callback(message)
                    except Exception as e:
                        logger.error(f"Error in message callback {callback_name}: {e}")
                    continue
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"Error in reader task {self._reader_task}: {e}")
        logger.info("Helios transport reader task stopped!")

    async def _run_writer_task(self) -> None:
        while self._writer is not None:
            try:
                message = await self._write_queue.get()
                await self.write_payload(message)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"Error in writer task {self._writer_task}: {e}")
        logger.info("Helios transport writer task stopped!")

    def register_message_callback(self, message_type: str, callback: Callable[[TransportMessage], None]) -> None:
        """Registers a callback for a specific message type."""
        self._message_callbacks[message_type] = callback

    def unregister_message_callback(self, message_type: str) -> None:
        """Unregisters a callback for a specific message type."""
        self._message_callbacks.pop(message_type, None)

    async def disconnect(self) -> None:
        """Disconnects from the Helios transport layer."""
        await self.reset()

    async def reset(self) -> None:
        """Resets the transport layer."""
        # Cancel the reader and writer tasks
        for task in (self._reader_task, self._writer_task):
            if task is not None and not task.done():
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
        self._reader_task = None
        self._writer_task = None

        # Close the writer and wait for it to be closed
        writer = self._writer
        self._reader = None
        self._writer = None
        if writer is not None:
            writer.close()
            with contextlib.suppress(Exception):
                await writer.wait_closed()

    async def write_payload(self, message: TransportMessage) -> None:
        """Writes a payload to the transport layer."""
        payload = message.SerializeToString()

        if len(payload) > self.MAX_FRAME_BYTES:
            raise HeliosConnectionError("message too large to send")
        if self._writer is None:
            raise HeliosConnectionError("not connected")

        self._writer.write(struct.pack("!I", len(payload)) + payload)
        await self._writer.drain()

    async def read_payload(self) -> TransportMessage:
        """Reads a payload from the transport layer."""
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

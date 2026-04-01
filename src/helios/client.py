from __future__ import annotations

import asyncio

from generated.helios.transport import HandshakeRequest, HandshakeResponse

from helios.errors import ConnectionError as HeliosConnectionError
from helios.errors import HandshakeError
from helios.transport import HeliosTransport


class HeliosClient:
    """Async TCP client for the Helios transport protocol."""

    def __init__(
        self,
        core_address: str,
        core_port: int,
        node_uri: str,
        require_expected: bool = False,
    ) -> None:
        self._node_uri = node_uri
        self._require_expected = require_expected
        self._transport = HeliosTransport(core_address, core_port)

    async def _perform_handshake(self) -> bool:
        # Create and send handshake request
        request = HandshakeRequest(
            version=HeliosTransport.PROTOCOL_VERSION,
            client_address=self._node_uri,
            require_expected=self._require_expected,
        )

        try:
            await self._transport.write_framed_payload(
                request.SerializeToString()
            )
            raw_handshake_response = await self._transport.read_framed_payload()
        except asyncio.IncompleteReadError as e:
            raise HeliosConnectionError("connection closed during handshake") from e

        try:
            response = HandshakeResponse.parse(raw_handshake_response)
        except (TypeError, ValueError) as e:
            raise HandshakeError(f"invalid handshake response: {e}") from e

        if response.version != HeliosTransport.PROTOCOL_VERSION:
            raise HandshakeError(
                f"protocol version mismatch: server {response.version}, "
                f"client {HeliosTransport.PROTOCOL_VERSION}"
            )
        return True

    async def _reset_connection(self) -> None:
        await self._transport.reset()

    async def connect(self) -> None:
        if self._transport.is_connected:
            raise HeliosConnectionError("already connected")
        try:
            await self._transport.connect()
            if not await self._perform_handshake():
                raise HandshakeError("failed to perform handshake")
        except Exception as e:
            await self._reset_connection()
            raise HeliosConnectionError(f"failed to connect: {e}") from e

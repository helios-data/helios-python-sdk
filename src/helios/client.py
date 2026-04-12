from __future__ import annotations

import asyncio
import uuid

from generated.helios.transport import (
    Event,
    EventPublish,
    HandshakeRequest,
    EventRequest,
    TransportMessage,
)

from helios.errors import ConnectionError as HeliosConnectionError
from helios.errors import HandshakeError
from helios.transport import HeliosTransport

import logging

logger = logging.getLogger(__name__)

class HeliosClient:
    """Async TCP client for the Helios transport protocol."""

    def __init__(
        self,
        core_address: str,
        core_port: int,
        node_uri: str,
        *,
        must_be_registered: bool = False,
        async_publish: bool = True,
        use_background_io: bool = True,
    ) -> None:
        self._node_uri = node_uri
        self._must_be_registered = must_be_registered
        self._async_publish = async_publish
        self._use_background_io = use_background_io
        self._sequence_number = 0
        self._pending_requests: dict[str, asyncio.Future[Event]] = {}
        self._transport = HeliosTransport(core_address, core_port)

    async def connect(self) -> None:
        """Connects to the Helios transport layer, and performs the handshake with the Helios core."""

        if self._transport.is_connected:
            raise HeliosConnectionError("Cannot connect to Helios: Already connected")
        try:
            # Connect to the transport
            await self._transport.connect()
            if not await self._perform_handshake():
                raise HandshakeError("Failed to perform handshake with Helios")

            # Start background tasks if needed
            if self._use_background_io:
                await self._transport.start_tasks()

                # Register message callbacks
                self._transport.register_message_callback(
                    "request_response",
                    self._handle_request_response,
                )

        except Exception as e:
            await self._reset_connection()
            raise e

    async def _perform_handshake(self) -> bool:
        # Create handshake request
        request = HandshakeRequest(
            version=HeliosTransport.PROTOCOL_VERSION,
            client_address=self._node_uri,
            must_be_registered=self._must_be_registered,
        )
        outgoing = TransportMessage(handshake_request=request)

        # Send handshake request to Helios, and then wait for handshake response
        try:
            await self._transport.write_payload(outgoing)
            envelope = await self._transport.read_payload()
        except asyncio.IncompleteReadError as e:
            raise HeliosConnectionError("Connection closed during handshake") from e
        except (TypeError, ValueError) as e:
            raise HandshakeError(f"Invalid handshake response: {e}") from e

        # Parse and validate handshake response
        response = envelope.handshake_response
        if response is None:
            raise HandshakeError(
                "Invalid handshake response: expected handshake_response in "
                "TransportMessage"
            )

        if response.version != HeliosTransport.PROTOCOL_VERSION:
            raise HandshakeError(
                f"Protocol version mismatch: server {response.version}, "
                f"client {HeliosTransport.PROTOCOL_VERSION}"
            )
        return True

    def _handle_request_response(self, message: TransportMessage) -> None:
        """Captures incoming request/response messages from Helios, and sets the result of the pending request."""
        if message.event_publish is not None:
            pub = message.event_publish
            rid = pub.request_id
            if rid is not None and rid in self._pending_requests:
                self._pending_requests[rid].set_result(pub.event)
                del self._pending_requests[rid]

    async def _reset_connection(self) -> None:
        await self._transport.reset()

    async def publish_event(
        self,
        *,
        address: str,
        event_type: str,
        data: bytes,
        event_id: int | None = None
    ) -> None:
        """Publishes an event to the Helios transport layer.

        Args:
            address: The address of the event to publish to.
            event_type: The type of the event to publish.
            data: The data of the event to publish.
            event_id: The ID of the event to publish. If not provided, a new sequence number will be generated.
        """
        if not self._transport.is_connected:
            raise HeliosConnectionError("Failed to publish event: Not connected to Helios")

        event_id = event_id if event_id is not None else self._sequence_number
        self._sequence_number += 1

        event = Event(
            id=event_id,
            event_type=event_type,
            source_address=self._node_uri,
            data=data,
        )
        publish = EventPublish(
            address=address,
            event_type=event_type,
            event=event
        )
        message = TransportMessage(event_publish=publish)

        if self._async_publish and self._use_background_io:
            await self._transport.enqueue_outgoing(message)
        else:
            try:
                await self._transport.write_payload(message)
            except Exception as e:
                raise HeliosConnectionError("Failed to publish event: Failed to write payload") from e

    async def get_event(
        self,
        *,
        address: str,
        event_type: str
    ) -> Event:
        """Gets an event from the Helios transport layer.

        Args:
            address: The address of the event to get.
            event_type: The type of the event to get.

        Returns:
            A future that will be resolved with the event that was received from the Helios transport layer.
        """
        if not self._transport.is_connected:
            raise HeliosConnectionError("Failed to get event: Not connected to Helios")

        # Generate a random request ID
        request_id = str(uuid.uuid4())

        # Create a future to hold the result of the request,
        # which will be resolved when the event is received from the Helios transport layer.
        pending_future: asyncio.Future[Event] = asyncio.Future()
        self._pending_requests[request_id] = pending_future
        message = TransportMessage(
            event_request=EventRequest(
                address=address,
                event_type=event_type,
                request_id=request_id,
            )
        )
        if self._async_publish and self._use_background_io:
            await self._transport.enqueue_outgoing(message)
        else:
            await self._transport.write_payload(message)
        return await pending_future

    async def disconnect(self) -> None:
        await self._transport.disconnect()

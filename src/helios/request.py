from __future__ import annotations

import asyncio
import uuid

from .generated.helios.transport import Event, TransportMessage


class RequestManager:
    """Tracks pending get_event requests and applies EventPublish replies."""

    def __init__(self) -> None:
        self._pending_requests: dict[str, asyncio.Future[Event]] = {}

    def handle_incoming(self, message: TransportMessage) -> bool:
        """Apply a get_event reply if applicable. Returns True when this frame was consumed."""
        if message.event_publish is None:
            return False
        pub = message.event_publish
        rid = pub.request_id
        if rid is not None and rid in self._pending_requests:
            self._pending_requests[rid].set_result(pub.event)
            self._pending_requests.pop(rid, None)
            return True
        return False

    def create_event(self) -> tuple[str, asyncio.Future[Event]]:
        """Allocate request_id and a future; caller sends EventRequest and awaits the future."""
        request_id = str(uuid.uuid4())
        pending_future: asyncio.Future[Event] = asyncio.Future()
        self._pending_requests[request_id] = pending_future
        return request_id, pending_future

    def clear_all(self) -> None:
        for fut in self._pending_requests.values():
            if not fut.done():
                fut.cancel()
        self._pending_requests.clear()

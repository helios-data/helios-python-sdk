"""Subscription delivery: one :class:`Subscription` per ``subscription_id``."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import uuid
from collections.abc import AsyncIterator

from generated.helios.transport import Event, TransportMessage

logger = logging.getLogger(__name__)


class Subscription:
    """Buffered stream of Event values for a single Helios subscription."""

    def __init__(self, queue_maxlen: int | None) -> None:
        if queue_maxlen is not None and queue_maxlen < 0:
            raise ValueError("queue_maxlen must be None or >= 0")
        if queue_maxlen is None:
            self._queue: asyncio.Queue[Event | None] = asyncio.Queue()
        else:
            cap = 1 if queue_maxlen == 0 else queue_maxlen
            self._queue = asyncio.Queue(maxsize=cap)

    def put_event(self, event: Event) -> None:
        while True:
            try:
                self._queue.put_nowait(event)
                return
            except asyncio.QueueFull:
                try:
                    self._queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass

    def close(self) -> None:
        """Signal end of stream (async for over events stops)."""
        while True:
            try:
                self._queue.put_nowait(None)
                return
            except asyncio.QueueFull:
                try:
                    self._queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass

    async def events(self) -> AsyncIterator[Event]:
        while True:
            item = await self._queue.get()
            if item is None:
                break
            yield item


class SubscriptionManager:
    """Creates and manages subscriptions. Handles incoming EventPublish messages and delivers them to the appropriate Subscription."""

    def __init__(self) -> None:
        self._subscriptions: dict[str, Subscription] = {}

    def create_subscription(self, *, queue_maxlen: int | None) -> tuple[str, Subscription]:
        """Allocate subscription_id and a Subscription; caller sends EventSubscribe."""
        subscription_id = str(uuid.uuid4())
        sub = Subscription(queue_maxlen)
        self._subscriptions[subscription_id] = sub
        return subscription_id, sub

    def remove_subscription(self, subscription_id: str) -> None:
        self._subscriptions.pop(subscription_id, None)

    def handle_incoming(
        self, message: TransportMessage
    ) -> None:
        if message.event_publish is None:
            return
        pub = message.event_publish
        sid = (pub.subscription_id or "").strip()
        if not sid:
            return
        sub = self._subscriptions.get(sid)
        if sub is None:
            return
        ev = pub.event
        if ev is not None:
            try:
                sub.put_event(ev)
            except Exception as e:
                logger.warning("subscription delivery failed: %s", e)

    def close_all(self) -> None:
        for sub in self._subscriptions.values():
            with contextlib.suppress(Exception):
                sub.close()
        self._subscriptions.clear()

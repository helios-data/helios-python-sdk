"""Helios SDK exception types."""

from __future__ import annotations


class HeliosError(Exception):
    """Base exception for all Helios SDK errors."""


class ConnectionError(HeliosError):
    """Raised when a WebSocket connection to the core fails."""


class HandshakeError(ConnectionError):
    """Raised when the handshake with the Helios core fails."""


class EventError(HeliosError):
    """Wraps an EventError proto message received from the core."""

    def __init__(
        self,
        address: str,
        event_type: str,
        error_code: int,
        message: str,
        request_id: str | None = None,
    ) -> None:
        self.address = address
        self.event_type = event_type
        self.error_code = error_code
        self.request_id = request_id
        super().__init__(message)

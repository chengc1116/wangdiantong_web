"""Exceptions raised by the WangDian SDK."""

from typing import Any, Mapping, Optional


class WangdianError(Exception):
    """Base class for all SDK errors."""


class ConfigurationError(WangdianError, ValueError):
    """Raised when client configuration or input is invalid."""


class TransportError(WangdianError):
    """Raised when an HTTP request cannot be completed successfully."""

    def __init__(
        self,
        message: str,
        *,
        url: str,
        status_code: Optional[int] = None,
    ) -> None:
        super().__init__(message)
        self.url = url
        self.status_code = status_code


class ResponseDecodeError(WangdianError):
    """Raised when the API response is not a JSON object."""

    def __init__(self, message: str, *, response_text: str = "") -> None:
        super().__init__(message)
        self.response_text = response_text


class ApiError(WangdianError):
    """Raised when WangDian returns a non-zero business error code."""

    def __init__(
        self,
        code: Any,
        message: str,
        *,
        response: Mapping[str, Any],
    ) -> None:
        super().__init__(f"WangDian API error {code}: {message}")
        self.code = code
        self.message = message
        self.response = response


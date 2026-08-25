"""Synchronous client for WangDian ERP Web OpenAPI."""

import json
import re
import threading
import time
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, Mapping, Optional, Union

import requests

from .exceptions import (
    ApiError,
    ConfigurationError,
    ResponseDecodeError,
    TransportError,
)
from .signing import generate_sign


class Environment(str, Enum):
    """Official WangDian Web OpenAPI environments."""

    TEST = "test"
    PRODUCTION = "production"


BASE_URLS = {
    Environment.TEST: "https://openapi.ali.huice.cc/openapi",
    Environment.PRODUCTION: "https://openapi.huice.com/openapi",
}

_ENVIRONMENT_ALIASES = {
    "test": Environment.TEST,
    "testing": Environment.TEST,
    "sandbox": Environment.TEST,
    "prod": Environment.PRODUCTION,
    "production": Environment.PRODUCTION,
    "formal": Environment.PRODUCTION,
}
_ENDPOINT_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
_RESERVED_PARAMETERS = frozenset({"sid", "appkey", "timestamp", "sign"})


def _resolve_environment(value: Union[Environment, str]) -> Environment:
    if isinstance(value, Environment):
        return value
    try:
        return _ENVIRONMENT_ALIASES[value.strip().lower()]
    except (AttributeError, KeyError) as exc:
        choices = ", ".join(sorted(_ENVIRONMENT_ALIASES))
        raise ConfigurationError(
            f"unknown environment {value!r}; expected one of: {choices}"
        ) from exc


def _serialize_value(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, bytes):
        return value.decode("utf-8")
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, (Mapping, list, tuple)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if isinstance(value, (int, float, Decimal)):
        return str(value)
    raise ConfigurationError(
        f"unsupported parameter type {type(value).__name__}; "
        "use a string, number, date, mapping, list, tuple, bool, or None"
    )


class WangdianClient:
    """Client that signs and sends requests to any standard API endpoint."""

    def __init__(
        self,
        sid: str,
        app_key: str,
        app_secret: str,
        *,
        environment: Union[Environment, str] = Environment.PRODUCTION,
        base_url: Optional[str] = None,
        timeout: Union[float, tuple] = 30.0,
        session: Optional[requests.Session] = None,
        raise_on_api_error: bool = True,
        requests_per_minute: Optional[float] = None,
    ) -> None:
        for field_name, value in (
            ("sid", sid),
            ("app_key", app_key),
            ("app_secret", app_secret),
        ):
            if not isinstance(value, str) or not value:
                raise ConfigurationError(f"{field_name} must be a non-empty string")

        self.sid = sid
        self.app_key = app_key
        self._app_secret = app_secret
        self.environment = _resolve_environment(environment)
        self.base_url = (base_url or BASE_URLS[self.environment]).rstrip("/")
        if not self.base_url.startswith(("https://", "http://")):
            raise ConfigurationError("base_url must start with http:// or https://")
        self.timeout = timeout
        self.raise_on_api_error = raise_on_api_error
        if requests_per_minute is not None and requests_per_minute <= 0:
            raise ConfigurationError("requests_per_minute must be greater than zero")
        self._request_interval = (
            60.0 / requests_per_minute if requests_per_minute is not None else 0.0
        )
        self._last_request_started: Optional[float] = None
        self._rate_limit_lock = threading.Lock()
        self.session = session or requests.Session()
        self._owns_session = session is None
        self.session.headers.setdefault(
            "User-Agent", "wangdian-python-sdk/0.1.0"
        )
        self.session.headers.setdefault(
            "Content-Type", "application/x-www-form-urlencoded; charset=utf-8"
        )

    def __enter__(self) -> "WangdianClient":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def close(self) -> None:
        """Close the internally-created HTTP session."""

        if self._owns_session:
            self.session.close()

    def endpoint_url(self, endpoint: str) -> str:
        """Build an endpoint URL from a service name or ``.php`` filename."""

        if not isinstance(endpoint, str):
            raise ConfigurationError("endpoint must be a string")
        service_name = endpoint.strip()
        if service_name.endswith(".php"):
            service_name = service_name[:-4]
        if not _ENDPOINT_PATTERN.fullmatch(service_name):
            raise ConfigurationError(
                "endpoint may contain only letters, numbers, and underscores"
            )
        return f"{self.base_url}/{service_name}.php"

    def build_parameters(
        self,
        parameters: Optional[Mapping[str, Any]] = None,
        *,
        timestamp: Optional[int] = None,
    ) -> Dict[str, str]:
        """Serialize business parameters and add authentication fields."""

        business_parameters = parameters or {}
        if not isinstance(business_parameters, Mapping):
            raise ConfigurationError("parameters must be a mapping")

        conflicts = _RESERVED_PARAMETERS.intersection(business_parameters)
        if conflicts:
            fields = ", ".join(sorted(conflicts))
            raise ConfigurationError(
                f"authentication parameters are managed by the SDK: {fields}"
            )

        payload: Dict[str, str] = {}
        for key, value in business_parameters.items():
            if not isinstance(key, str) or not key:
                raise ConfigurationError("parameter names must be non-empty strings")
            if value is not None:
                payload[key] = _serialize_value(value)

        request_timestamp = int(time.time()) if timestamp is None else timestamp
        if isinstance(request_timestamp, bool) or not isinstance(request_timestamp, int):
            raise ConfigurationError("timestamp must be an integer Unix timestamp")

        payload.update(
            {
                "sid": self.sid,
                "appkey": self.app_key,
                "timestamp": str(request_timestamp),
            }
        )
        payload["sign"] = generate_sign(payload, self._app_secret)
        return payload

    def call(
        self,
        endpoint: str,
        parameters: Optional[Mapping[str, Any]] = None,
        *,
        timestamp: Optional[int] = None,
        raise_on_api_error: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Call a WangDian API service and return its decoded JSON object."""

        url = self.endpoint_url(endpoint)
        with self._rate_limit_lock:
            if self._last_request_started is not None and self._request_interval:
                now = time.monotonic()
                delay = self._request_interval - (now - self._last_request_started)
                if delay > 0:
                    time.sleep(delay)
                    now += delay
                self._last_request_started = now
            else:
                self._last_request_started = time.monotonic()

            payload = self.build_parameters(parameters, timestamp=timestamp)
            try:
                response = self.session.post(url, data=payload, timeout=self.timeout)
                response.raise_for_status()
            except requests.RequestException as exc:
                status_code = getattr(getattr(exc, "response", None), "status_code", None)
                raise TransportError(
                    f"request to WangDian failed: {exc}",
                    url=url,
                    status_code=status_code,
                ) from exc

        try:
            result = response.json()
        except (requests.JSONDecodeError, ValueError) as exc:
            raise ResponseDecodeError(
                "WangDian returned a non-JSON response",
                response_text=response.text,
            ) from exc
        if not isinstance(result, dict):
            raise ResponseDecodeError(
                "WangDian returned JSON that is not an object",
                response_text=response.text,
            )

        should_raise = (
            self.raise_on_api_error
            if raise_on_api_error is None
            else raise_on_api_error
        )
        code = result.get("code")
        if should_raise and code is not None and str(code) != "0":
            message = str(result.get("message", result.get("msg", "unknown error")))
            raise ApiError(code, message, response=result)
        return result

    request = call

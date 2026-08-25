import unittest
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, Optional

import requests
from unittest.mock import patch

from wangdian import (
    ApiError,
    ConfigurationError,
    Environment,
    ResponseDecodeError,
    TransportError,
    WangdianClient,
)


class FakeResponse:
    def __init__(
        self,
        data: Any = None,
        *,
        text: str = "",
        status_code: int = 200,
        json_error: Optional[Exception] = None,
    ) -> None:
        self.data = data
        self.text = text
        self.status_code = status_code
        self.json_error = json_error

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            response = requests.Response()
            response.status_code = self.status_code
            raise requests.HTTPError("HTTP error", response=response)

    def json(self) -> Any:
        if self.json_error:
            raise self.json_error
        return self.data


class FakeSession:
    def __init__(self, response: FakeResponse) -> None:
        self.headers: Dict[str, str] = {}
        self.response = response
        self.last_request: Optional[Dict[str, Any]] = None
        self.closed = False

    def post(self, url: str, **kwargs: Any) -> FakeResponse:
        self.last_request = {"url": url, **kwargs}
        return self.response

    def close(self) -> None:
        self.closed = True


def make_client(response: FakeResponse, **kwargs: Any) -> WangdianClient:
    return WangdianClient(
        "seller",
        "app-key",
        "secret",
        session=FakeSession(response),  # type: ignore[arg-type]
        **kwargs,
    )


class ClientTests(unittest.TestCase):
    def test_environment_urls(self) -> None:
        production = WangdianClient("s", "k", "x")
        testing = WangdianClient("s", "k", "x", environment="sandbox")
        try:
            self.assertEqual(production.environment, Environment.PRODUCTION)
            self.assertEqual(
                production.endpoint_url("trade_query"),
                "https://openapi.huice.com/openapi/trade_query.php",
            )
            self.assertEqual(
                testing.endpoint_url("shop.php"),
                "https://openapi.ali.huice.cc/openapi/shop.php",
            )
        finally:
            production.close()
            testing.close()

    def test_serializes_parameters_before_signing(self) -> None:
        client = make_client(FakeResponse({"code": 0, "shops": []}))
        result = client.call(
            "shop",
            {
                "filters": {"name": "中文"},
                "items": [1, "二"],
                "enabled": True,
                "amount": Decimal("10.20"),
                "day": date(2026, 7, 30),
                "created": datetime(2026, 7, 30, 10, 20, 30),
                "ignored": None,
            },
            timestamp=1470042310,
        )

        self.assertEqual(result["code"], 0)
        request = client.session.last_request  # type: ignore[attr-defined]
        self.assertEqual(
            request["url"], "https://openapi.huice.com/openapi/shop.php"
        )
        payload = request["data"]
        self.assertEqual(payload["filters"], '{"name":"中文"}')
        self.assertEqual(payload["items"], '[1,"二"]')
        self.assertEqual(payload["enabled"], "1")
        self.assertEqual(payload["amount"], "10.20")
        self.assertEqual(payload["day"], "2026-07-30")
        self.assertEqual(payload["created"], "2026-07-30 10:20:30")
        self.assertNotIn("ignored", payload)
        self.assertEqual(len(payload["sign"]), 32)

    def test_raises_api_error(self) -> None:
        client = make_client(FakeResponse({"code": 2900, "message": "参数错误"}))
        with self.assertRaises(ApiError) as context:
            client.call("trade_query")
        self.assertEqual(context.exception.code, 2900)
        self.assertEqual(context.exception.message, "参数错误")

    def test_can_return_api_error_response(self) -> None:
        client = make_client(FakeResponse({"code": "2900", "message": "bad"}))
        result = client.call("trade_query", raise_on_api_error=False)
        self.assertEqual(result["code"], "2900")

    def test_wraps_http_errors(self) -> None:
        client = make_client(FakeResponse(status_code=503))
        with self.assertRaises(TransportError) as context:
            client.call("shop")
        self.assertEqual(context.exception.status_code, 503)

    def test_rejects_non_object_json(self) -> None:
        client = make_client(FakeResponse([]))
        with self.assertRaises(ResponseDecodeError):
            client.call("shop")

    def test_rejects_reserved_parameters_and_invalid_endpoint(self) -> None:
        client = make_client(FakeResponse({"code": 0}))
        with self.assertRaises(ConfigurationError):
            client.build_parameters({"sign": "fake"})
        with self.assertRaises(ConfigurationError):
            client.endpoint_url("../shop")

    def test_does_not_close_external_session(self) -> None:
        session = FakeSession(FakeResponse({"code": 0}))
        client = WangdianClient(
            "seller", "key", "secret", session=session  # type: ignore[arg-type]
        )
        client.close()
        self.assertFalse(session.closed)

    def test_rate_limits_consecutive_requests(self) -> None:
        client = make_client(
            FakeResponse({"code": 0}), requests_per_minute=60
        )
        with patch("wangdian.client.time.monotonic", side_effect=[100.0, 100.2]), patch(
            "wangdian.client.time.sleep"
        ) as sleep:
            client.call("shop")
            client.call("shop")
        sleep.assert_called_once()
        self.assertAlmostEqual(sleep.call_args.args[0], 0.8)


if __name__ == "__main__":
    unittest.main()

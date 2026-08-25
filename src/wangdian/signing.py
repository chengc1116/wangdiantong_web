"""Implementation of WangDian's standard OpenAPI signature algorithm."""

import hashlib
from typing import Mapping


def _utf8_length(value: str) -> int:
    return len(value.encode("utf-8"))


def _length_prefix(value: str, minimum_width: int) -> str:
    return str(_utf8_length(value)).zfill(minimum_width)


def signing_string(parameters: Mapping[str, str]) -> str:
    """Build the canonical string described by WangDian's Sign guide."""

    parts = []
    for key in sorted(parameters):
        value = parameters[key]
        if not isinstance(key, str) or not isinstance(value, str):
            raise TypeError("signing parameters must contain only string keys and values")
        parts.append(
            f"{_length_prefix(key, 2)}-{key}:"
            f"{_length_prefix(value, 4)}-{value}"
        )
    return ";".join(parts)


def generate_sign(parameters: Mapping[str, str], app_secret: str) -> str:
    """Return the lowercase MD5 signature expected by WangDian."""

    if not isinstance(app_secret, str) or not app_secret:
        raise ValueError("app_secret must be a non-empty string")
    source = signing_string(parameters) + app_secret
    return hashlib.md5(source.encode("utf-8")).hexdigest()


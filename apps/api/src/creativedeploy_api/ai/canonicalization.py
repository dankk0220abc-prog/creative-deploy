"""Phase 3A domain normalization and RFC 8785-compatible bounded JCS."""

from __future__ import annotations

import hashlib
import json
import math
import unicodedata
from datetime import UTC, datetime
from decimal import Decimal

from creativedeploy_api.ai.constants import CANONICALIZATION_VERSION

type CanonicalValue = None | bool | int | str | list["CanonicalValue"] | dict[str, "CanonicalValue"]


class CanonicalizationError(ValueError):
    """A request cannot be represented by the frozen canonicalization contract."""


def canonical_timestamp(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise CanonicalizationError("Timestamp must include a timezone.")
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def fixed_decimal(value: Decimal, *, scale: int) -> str:
    if not value.is_finite():
        raise CanonicalizationError("Decimal value must be finite.")
    quantum = Decimal(1).scaleb(-scale)
    quantized = value.quantize(quantum)
    if quantized != value:
        raise CanonicalizationError("Decimal value exceeds its fixed scale.")
    return f"{quantized:.{scale}f}"


def normalize_value(value: object) -> CanonicalValue:
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise CanonicalizationError("Floating-point value must be finite.")
        raise CanonicalizationError("Binary floating-point values are forbidden.")
    if isinstance(value, str):
        normalized = unicodedata.normalize("NFC", value)
        if any(0xD800 <= ord(character) <= 0xDFFF for character in normalized):
            raise CanonicalizationError("Unpaired Unicode surrogates are forbidden.")
        return normalized
    if isinstance(value, list):
        return [normalize_value(item) for item in value]
    if isinstance(value, dict):
        normalized_items: dict[str, CanonicalValue] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise CanonicalizationError("Object keys must be strings.")
            normalized_key = unicodedata.normalize("NFC", key)
            if normalized_key in normalized_items:
                raise CanonicalizationError("Normalization produced a duplicate object key.")
            normalized_items[normalized_key] = normalize_value(item)
        return normalized_items
    raise CanonicalizationError("Value type is not supported by phase3a-v1.")


def _sort_key(value: str) -> bytes:
    return value.encode("utf-16-be")


def _jcs(value: CanonicalValue) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if isinstance(value, list):
        return "[" + ",".join(_jcs(item) for item in value) + "]"
    return (
        "{"
        + ",".join(f"{_jcs(key)}:{_jcs(value[key])}" for key in sorted(value, key=_sort_key))
        + "}"
    )


def canonicalize_and_hash(payload: object) -> tuple[bytes, str]:
    canonical = _jcs(normalize_value(payload)).encode("utf-8")
    return canonical, f"sha256:{hashlib.sha256(canonical).hexdigest()}"


__all__ = [
    "CANONICALIZATION_VERSION",
    "CanonicalizationError",
    "canonical_timestamp",
    "canonicalize_and_hash",
    "fixed_decimal",
    "normalize_value",
]

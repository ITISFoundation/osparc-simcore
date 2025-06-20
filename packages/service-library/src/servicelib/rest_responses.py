import json
from collections.abc import Mapping
from typing import Any

from common_library.json_serialization import json_loads

_ENVELOPE_KEYS = ("data", "error")


def is_enveloped_from_map(payload: Mapping) -> bool:
    return all(k in _ENVELOPE_KEYS for k in payload if not f"{k}".startswith("_"))


def is_enveloped_from_text(text: str) -> bool:
    try:
        payload = json_loads(text)
    except json.decoder.JSONDecodeError:
        return False
    return is_enveloped_from_map(payload)


def is_enveloped(payload: Mapping | str) -> bool:
    # pylint: disable=isinstance-second-argument-not-valid-type
    if isinstance(payload, Mapping):
        return is_enveloped_from_map(payload)
    if isinstance(payload, str):
        return is_enveloped_from_text(text=payload)
    return False  # type: ignore[unreachable]


def unwrap_envelope(payload: Mapping[str, Any]) -> tuple:
    """
    Safe returns (data, error) tuple from a response payload
    """
    return tuple(payload.get(k) for k in _ENVELOPE_KEYS) if payload else (None, None)


def unwrap_envelope_if_required(data: Mapping) -> Mapping:
    if is_enveloped(data):
        data, error = unwrap_envelope(data)
        assert not error  # nosec
    return data

"""Redaction of values that must not leak into logs, error payloads or task metadata"""

from typing import Final

_FROM: Final[int] = 3
_TO: Final[int] = -1
_MIN_NUM_DIGITS: Final[int] = 5


def mask_phone_number(phone: str) -> str:
    """Masks the digits of a phone number, keeping the '+' with the country
    code and the last digit, e.g. "+41791234567" -> "+41XXXXXXXX7"
    """
    assert len(phone) > _MIN_NUM_DIGITS  # nosec
    # SEE https://en.wikipedia.org/wiki/E.164
    return phone[:_FROM] + len(phone[_FROM:_TO]) * "X" + phone[_TO:]

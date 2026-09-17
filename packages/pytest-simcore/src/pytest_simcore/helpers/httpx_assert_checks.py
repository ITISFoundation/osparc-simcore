"""Extends assertions for testing"""

import re
from http import HTTPStatus
from pprint import pformat
from typing import Any

import httpx2
from models_library.generics import Envelope
from pydantic import TypeAdapter
from servicelib.aiohttp import status
from servicelib.status_codes_utils import get_code_display_name, is_error


def assert_status[T](
    response: httpx2.Response,
    expected_status_code: int,
    response_model: type[T] | None,
    *,
    expected_msg: str | None = None,
    expect_envelope: bool = True,
) -> tuple[T | None, Any]:
    """
    Asserts for enveloped responses
    """
    # raises ValueError if cannot be converted
    expected_status_code = HTTPStatus(expected_status_code)

    assert response.status_code == expected_status_code, (
        f"received {response.status_code}: {response.text}, expected {get_code_display_name(expected_status_code)}"
    )

    # response
    if expected_status_code == status.HTTP_204_NO_CONTENT:
        assert not response.text
        return None, None
    if expect_envelope:
        validated_response = TypeAdapter(Envelope[response_model]).validate_json(response.text)
        data = validated_response.data
        error = validated_response.error
        if is_error(expected_status_code):
            _do_assert_error(
                data,
                error,
                expected_status_code,
                expected_msg,
            )
        else:
            assert data is not None
        return data, error

    if is_error(expected_status_code):
        msg = "If you need it implement it"
        raise NotImplementedError(msg)

    data = TypeAdapter(response_model).validate_json(response.text)
    return data, None


def _do_assert_error(
    data,
    error,
    expected_status_code: int,
    expected_msg: list[str] | str | list[re.Pattern[str]] | re.Pattern[str] | None,
) -> None:
    assert not data, pformat(data)
    assert error, pformat(error)

    assert is_error(expected_status_code)

    details = error.get("errors", [])
    assert isinstance(details, list)

    if expected_msg:
        assert details is not None
        # find the expected msg are in the details
        list_expected_msg = expected_msg if isinstance(expected_msg, list) else [expected_msg]

        for msg in list_expected_msg:
            assert any(msg == e or re.search(msg, e) for e in details), f"could not find {msg=} in {details=}"

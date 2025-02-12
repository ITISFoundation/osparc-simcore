"""Extends assertions for testing"""

import re
from http import HTTPStatus
from pprint import pformat
from typing import Any, TypeVar

import httpx
from models_library.generics import Envelope
from pydantic import TypeAdapter
from servicelib.aiohttp import status
from servicelib.status_codes_utils import get_code_display_name, is_error

T = TypeVar("T")


def assert_status(
    response: httpx.Response,
    expected_status_code: int,
    response_model: type[T] | None,
    *,
    expected_msg: str | None = None,
    is_enveloped: bool = True,
) -> tuple[T | None, Any]:
    """
    Asserts for enveloped responses
    """
    # raises ValueError if cannot be converted
    expected_status_code = HTTPStatus(expected_status_code)

    assert (
        response.status_code == expected_status_code
    ), f"received {response.status_code}: {response.text}, expected {get_code_display_name(expected_status_code)}"

    # reponse
    if expected_status_code == status.HTTP_204_NO_CONTENT:
        assert response.text == ""
        return None, None
    if is_enveloped:
        validated_response = TypeAdapter(Envelope[response_model]).validate_json(
            response.text
        )
        data = validated_response.data
        error = validated_response.error
        if is_error(expected_status_code):
            _do_assert_error(
                data,
                error,
                expected_status_code,
                expected_msg,
            )
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
        if isinstance(expected_msg, list):
            list_expected_msg = expected_msg
        else:
            list_expected_msg = [expected_msg]

        for msg in list_expected_msg:
            assert any(
                re.search(msg, e) for e in details
            ), f"could not find {msg=} in {details=}"

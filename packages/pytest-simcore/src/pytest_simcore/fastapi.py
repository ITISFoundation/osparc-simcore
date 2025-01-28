"""Extends assertions for testing"""

from http import HTTPStatus
from pprint import pformat
from typing import Any, TypeVar

import httpx
from fastapi import FastAPI
from models_library.generics import Envelope
from pydantic import TypeAdapter
from servicelib.aiohttp import status
from servicelib.status_codes_utils import get_code_display_name, is_error
from yarl import URL

T = TypeVar("T")


async def assert_status(
    response: httpx.Response,
    expected_status_code: int,
    response_model: type[T],
    *,
    expected_msg: str | None = None,
    expected_error_code: str | None = None,
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
    if is_enveloped:
        validated_response = TypeAdapter(Envelope[response_model]).validate_json(
            response.text
        )
        data = validated_response.data
        error = validated_response.error
        if is_error(expected_status_code):
            _do_assert_error(
                data, error, expected_status_code, expected_msg, expected_error_code
            )
        return data, error
    if expected_status_code == status.HTTP_204_NO_CONTENT:
        assert response.text == ""
        return None, None

    if is_error(expected_status_code):
        msg = "If you need it implement it"
        raise NotImplementedError(msg)

    data = TypeAdapter(response_model).validate_json(response.text)
    return data, None


def _do_assert_error(
    data,
    error,
    expected_status_code: int,
    expected_msg: str | None = None,
    expected_error_code: str | None = None,
):
    assert not data, pformat(data)
    assert error, pformat(error)

    assert is_error(expected_status_code)

    # New versions of the error models might not have this attribute
    details = error.get("errors", [])

    if expected_msg:
        assert details
        messages = [e["message"] for e in details]
        assert expected_msg in messages

    if expected_error_code:
        assert details
        codes = [e["code"] for e in details]
        assert expected_error_code in codes

    return data, error


def url_from_operation_id(
    client: httpx.AsyncClient, app: FastAPI, operation_id: str, **path_params
) -> URL:
    return URL(f"{client.base_url}").with_path(
        app.url_path_for(operation_id, **path_params)
    )

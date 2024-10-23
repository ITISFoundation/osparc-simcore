# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import http

import pytest
from fastapi import FastAPI, HTTPException
from httpx import AsyncClient
from models_library.api_schemas__common.errors import DefaultApiError
from pydantic import TypeAdapter
from servicelib.fastapi.exceptions_utils import (
    handle_errors_as_500,
    http_exception_as_json_response,
)

_MIN_ERROR_STATUS_CODE = 400


builtin_exceptions = {
    f"{exc.__class__.__name__}": exc
    for exc in [
        # https://docs.python.org/3/library/exceptions.html#base-classes
        Exception(),
        ArithmeticError(),
        BufferError(),
        LookupError(),
        # https://docs.python.org/3/library/exceptions.html#concrete-exceptions
        NotImplementedError(),
        ValueError("wrong value"),
    ]
}

http_exceptions = {
    status_code: HTTPException(status_code=status_code, detail=f"test {status_code}")
    for status_code in [
        e.value for e in http.HTTPStatus if e.value >= _MIN_ERROR_STATUS_CODE
    ]
}


@pytest.fixture
def app() -> FastAPI:

    app = FastAPI()
    app.add_exception_handler(Exception, handle_errors_as_500)
    app.add_exception_handler(HTTPException, http_exception_as_json_response)

    @app.post("/error/{code}")
    async def raise_http_exception(code: int):
        raise http_exceptions[code]

    @app.post("/raise/{code}")
    async def raise_exception(code: str):
        raise builtin_exceptions[code]

    return app


@pytest.mark.parametrize("code,exception", list(http_exceptions.items()))
async def test_http_errors_respond_with_error_model(
    client: AsyncClient, code: int, exception: HTTPException
):
    response = await client.post(f"/error/{code}")
    assert response.status_code == code

    error = TypeAdapter(DefaultApiError).validate_json(response.text)
    assert error.detail == f"test {code}"
    assert error.name


@pytest.mark.xfail
@pytest.mark.parametrize("code,exception", list(builtin_exceptions.items()))
async def test_non_http_error_handling(
    client: AsyncClient, code: int | str, exception: BaseException
):
    response = await client.post(f"/raise/{code}")
    print(response)

    error = TypeAdapter(DefaultApiError).validate_json(response.text)

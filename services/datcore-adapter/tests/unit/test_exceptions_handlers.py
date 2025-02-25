# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from collections.abc import AsyncIterator

import httpx
import pytest
from botocore.exceptions import ClientError
from fastapi import FastAPI, HTTPException, status
from fastapi.exceptions import RequestValidationError
from httpx import AsyncClient
from pydantic import ValidationError
from pytest_simcore.helpers.httpx_assert_checks import assert_status
from simcore_service_datcore_adapter.errors.handlers import set_exception_handlers


@pytest.fixture
def initialized_app() -> FastAPI:
    app = FastAPI()
    set_exception_handlers(app)
    return app


@pytest.fixture
async def client(initialized_app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(
        transport=httpx.ASGITransport(app=initialized_app),
        base_url="http://test",
        headers={"Content-Type": "application/json"},
    ) as client:
        yield client


@pytest.mark.parametrize(
    "exception, status_code",
    [
        (
            ClientError(
                {
                    "Status": "pytest status",
                    "StatusReason": "pytest",
                    "Error": {
                        "Code": "NotAuthorizedException",
                        "Message": "pytest message",
                    },
                },
                operation_name="pytest operation",
            ),
            status.HTTP_401_UNAUTHORIZED,
        ),
        (
            ClientError(
                {
                    "Status": "pytest status",
                    "StatusReason": "pytest",
                    "Error": {
                        "Code": "Whatever",
                        "Message": "pytest message",
                    },
                },
                operation_name="pytest operation",
            ),
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ),
        (
            NotImplementedError("pytest not implemented error"),
            status.HTTP_501_NOT_IMPLEMENTED,
        ),
    ],
    ids=str,
)
async def test_exception_handlers(
    initialized_app: FastAPI,
    client: AsyncClient,
    exception: Exception,
    status_code: int,
):
    @initialized_app.get("/test")
    async def test_endpoint():
        raise exception

    response = await client.get("/test")
    assert_status(
        response,
        status_code,
        None,
        expected_msg=f"{exception}".replace("(", "\\(").replace(")", "\\)"),
    )


async def test_generic_http_exception_handler(
    initialized_app: FastAPI, client: AsyncClient
):
    @initialized_app.get("/test")
    async def test_endpoint():
        raise HTTPException(status_code=status.HTTP_410_GONE)

    response = await client.get("/test")
    assert_status(response, status.HTTP_410_GONE, None, expected_msg="Gone")


async def test_request_validation_error_handler(
    initialized_app: FastAPI, client: AsyncClient
):
    _error_msg = "pytest request validation error"

    @initialized_app.get("/test")
    async def test_endpoint():
        raise RequestValidationError(errors=[_error_msg])

    response = await client.get("/test")
    assert_status(
        response,
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        None,
        expected_msg=_error_msg,
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


async def test_validation_error_handler(initialized_app: FastAPI, client: AsyncClient):
    _error_msg = "pytest request validation error"

    @initialized_app.get("/test")
    async def test_endpoint():
        raise ValidationError.from_exception_data(
            _error_msg,
            line_errors=[],
        )

    response = await client.get("/test")
    assert_status(
        response,
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        None,
        expected_msg=f"0 validation errors for {_error_msg}",
    )


@pytest.mark.xfail(
    reason="Generic exception handler is not working as expected as shown in https://github.com/ITISFoundation/osparc-simcore/blob/5732a12e07e63d5ce55010ede9b9ab543bb9b278/packages/service-library/tests/fastapi/test_exceptions_utils.py"
)
async def test_generic_exception_handler(initialized_app: FastAPI, client: AsyncClient):
    _error_msg = "Generic pytest exception"

    @initialized_app.get("/test")
    async def test_endpoint():
        raise Exception(  # pylint: disable=broad-exception-raised # noqa: TRY002
            _error_msg
        )

    response = await client.get("/test")
    assert_status(
        response,
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        None,
        expected_msg=_error_msg,
    )

# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import pytest
from aiohttp import web
from aiohttp.typedefs import Handler
from aws_library.s3 import S3KeyNotFoundError
from pydantic import BaseModel, ValidationError
from pytest_mock import MockerFixture
from servicelib.aiohttp.aiopg_utils import DBAPIError
from simcore_service_storage.db_access_layer import InvalidFileIdentifierError
from simcore_service_storage.exceptions import (
    FileAccessRightError,
    FileMetaDataNotFoundError,
    ProjectAccessRightError,
    ProjectNotFoundError,
)
from simcore_service_storage.utils_handlers import dsm_exception_handler


@pytest.fixture()
async def raising_handler(
    mocker: MockerFixture, handler_exception: type[Exception]
) -> Handler:
    mock = mocker.patch("aiohttp.typedefs.Handler", autospec=True)
    mock.side_effect = handler_exception
    return mock


@pytest.fixture
def mock_request(mocker: MockerFixture) -> web.Request:
    return mocker.patch("aiohttp.web.Request", autospec=True)


class FakeErrorModel(BaseModel):
    dummy: int = 1


@pytest.mark.parametrize(
    "handler_exception, expected_web_response",
    [
        (InvalidFileIdentifierError(identifier="x"), web.HTTPUnprocessableEntity),
        (FileMetaDataNotFoundError(file_id="x"), web.HTTPNotFound),
        (S3KeyNotFoundError(key="x", bucket="x"), web.HTTPNotFound),
        (ProjectNotFoundError(project_id="x"), web.HTTPNotFound),
        (FileAccessRightError(file_id="x", access_right="x"), web.HTTPForbidden),
        (ProjectAccessRightError(project_id="x", access_right="x"), web.HTTPForbidden),
        (
            ValidationError.from_exception_data(title="test", line_errors=[]),
            web.HTTPUnprocessableEntity,
        ),
        (DBAPIError, web.HTTPServiceUnavailable),
    ],
)
async def test_dsm_exception_handler(
    mock_request: web.Request,
    raising_handler: Handler,
    expected_web_response: type[web.HTTPClientError],
):
    with pytest.raises(expected_web_response):
        await dsm_exception_handler(mock_request, raising_handler)

# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import logging

import pytest
from aiohttp import web
from aiohttp.test_utils import make_mocked_request
from servicelib.aiohttp import status
from simcore_service_webserver.errors import WebServerBaseError
from simcore_service_webserver.exceptions_handlers import (
    HttpErrorInfo,
    _sort_exceptions_by_specificity,
    create_exception_handlers_decorator,
)


class BasePluginError(WebServerBaseError):
    ...


class OneError(BasePluginError):
    ...


class OtherError(BasePluginError):
    ...


def test_sort_concrete_first():
    assert _sort_exceptions_by_specificity([Exception, BasePluginError]) == [
        BasePluginError,
        Exception,
    ]

    assert _sort_exceptions_by_specificity(
        [Exception, BasePluginError], concrete_first=False
    ) == [
        Exception,
        BasePluginError,
    ]


def test_sort_exceptions_by_specificity():

    got_exceptions_cls = _sort_exceptions_by_specificity(
        [
            Exception,
            OtherError,
            OneError,
            BasePluginError,
            ValueError,
            ArithmeticError,
            ZeroDivisionError,
        ]
    )

    for from_, exc in enumerate(got_exceptions_cls, start=1):
        for exc_after in got_exceptions_cls[from_:]:
            assert not issubclass(exc_after, exc), f"{got_exceptions_cls=}"


async def test_exception_handlers_decorator(
    caplog: pytest.LogCaptureFixture,
):

    _handle_exceptions = create_exception_handlers_decorator(
        exceptions_catch=BasePluginError,
        exc_to_status_map={
            OneError: HttpErrorInfo(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                msg_template="This is one error for front-end",
            )
        },
    )

    @_handle_exceptions
    async def _rest_handler(request: web.Request) -> web.Response:
        if request.query.get("raise") == "OneError":
            raise OneError
        if request.query.get("raise") == "ArithmeticError":
            raise ArithmeticError

        return web.Response(reason="all good")

    with caplog.at_level(logging.ERROR):

        # emulates successful call
        resp = await _rest_handler(make_mocked_request("GET", "/foo"))
        assert resp.status == status.HTTP_200_OK
        assert resp.reason == "all good"

        assert not caplog.records

        # this will be passed and catched by the outermost error middleware
        with pytest.raises(ArithmeticError):
            await _rest_handler(
                make_mocked_request("GET", "/foo?raise=ArithmeticError")
            )

        assert not caplog.records

        # this is a 5XX will be converted to response but is logged as error as well
        with pytest.raises(web.HTTPException) as exc_info:
            await _rest_handler(make_mocked_request("GET", "/foo?raise=OneError"))

        resp = exc_info.value
        assert resp.status == status.HTTP_503_SERVICE_UNAVAILABLE
        assert "front-end" in resp.reason

        assert caplog.records
        assert caplog.records[0].levelno == logging.ERROR

# pylint:disable=redefined-outer-name

import logging

import pytest

from common_library.error_codes import create_error_code
from common_library.errors_classes import OsparcErrorMixin
from servicelib.logging_errors import (
    create_troubleshotting_log_kwargs,
    create_troubleshotting_log_message,
)


def test_create_troubleshotting_log_message(caplog: pytest.LogCaptureFixture):
    class MyError(OsparcErrorMixin, RuntimeError):
        msg_template = "My error {user_id}"

    with pytest.raises(MyError) as exc_info:
        raise MyError(user_id=123, product_name="foo")

    exc = exc_info.value
    error_code = create_error_code(exc)

    assert exc.error_code() == error_code

    msg = f"Nice message to user [{error_code}]"

    log_msg = create_troubleshotting_log_message(
        msg,
        error=exc,
        error_code=error_code,
        error_context=exc.error_context(),
        tip="This is a test error",
    )

    log_kwargs = create_troubleshotting_log_kwargs(
        msg,
        error=exc,
        error_code=error_code,
        tip="This is a test error",
    )

    assert log_kwargs["msg"] == log_msg
    assert log_kwargs["extra"] is not None
    assert (
        # pylint: disable=unsubscriptable-object
        log_kwargs["extra"]["log_uid"]
        == "123"
    ), "user_id is injected as extra from context"

    with caplog.at_level(logging.WARNING):
        root_logger = logging.getLogger()
        root_logger.exception(**log_kwargs)

        # ERROR    root:test_logging_utils.py:417 Nice message to user [OEC:126055703573984].
        # {
        # "exception_details": "My error 123",
        # "error_code": "OEC:126055703573984",
        # "context": {
        #     "user_id": 123,
        #     "product_name": "foo"
        # },
        # "tip": "This is a test error"
        # }

        assert error_code in caplog.text
        assert "user_id" in caplog.text
        assert "product_name" in caplog.text

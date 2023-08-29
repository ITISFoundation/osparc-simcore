# pylint:disable=redefined-outer-name

import logging
from threading import Thread

import pytest
from pytest import LogCaptureFixture
from servicelib.logging_utils import (
    LogLevelInt,
    LogMessageStr,
    guess_message_log_level,
    log_decorator,
)
from servicelib.utils import logged_gather

logger = logging.getLogger(__name__)


@pytest.mark.parametrize("logger", [None, logger])
@pytest.mark.parametrize("log_traceback", [True, False])
async def test_error_regression_async_def(
    caplog: LogCaptureFixture, logger: logging.Logger | None, log_traceback: bool
):
    @log_decorator(logger, log_traceback=log_traceback)
    async def _raising_error() -> None:
        msg = "Raising as expected"
        raise RuntimeError(msg)

    caplog.clear()

    await logged_gather(_raising_error(), reraise=False)

    if log_traceback:
        assert "Traceback" in caplog.text
    else:
        assert "Traceback" not in caplog.text


@pytest.mark.parametrize("logger", [None, logger])
@pytest.mark.parametrize("log_traceback", [True, False])
async def test_error_regression_def(
    caplog: LogCaptureFixture, logger: logging.Logger | None, log_traceback: bool
):
    @log_decorator(logger, log_traceback=log_traceback)
    def _raising_error() -> None:
        msg = "Raising as expected"
        raise RuntimeError(msg)

    caplog.clear()

    thread = Thread(target=_raising_error)
    thread.start()
    thread.join()

    if log_traceback:
        assert "Traceback" in caplog.text
    else:
        assert "Traceback" not in caplog.text


@pytest.mark.parametrize(
    "message, expected_log_level",
    [
        ("", logging.INFO),
        ("Error: this is an error", logging.ERROR),
        ("[Error] this is an error", logging.ERROR),
        ("[Error]: this is an error", logging.ERROR),
        ("[Err] this is an error", logging.ERROR),
        ("[Err]: this is an error", logging.ERROR),
        ("Err: this is an error", logging.ERROR),
        ("Warning: this is an warning", logging.WARNING),
        ("[Warning] this is an warning", logging.WARNING),
        ("[Warning]: this is an warning", logging.WARNING),
        ("[Warn] this is an warning", logging.WARNING),
        ("[Warn]: this is an warning", logging.WARNING),
        ("Warn: this is an warning", logging.WARNING),
        ("Not a Warn: this is an warning", logging.INFO),
    ],
)
def test_guess_message_log_level(
    message: LogMessageStr, expected_log_level: LogLevelInt
):
    assert guess_message_log_level(message) == expected_log_level

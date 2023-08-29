# pylint:disable=redefined-outer-name

import logging
from threading import Thread
from typing import Any

import pytest
from servicelib.logging_utils import (
    LogLevelInt,
    LogMessageStr,
    guess_message_log_level,
    log_context,
    log_decorator,
)
from servicelib.utils import logged_gather

_logger = logging.getLogger(__name__)


@pytest.mark.parametrize("logger", [None, _logger])
@pytest.mark.parametrize("log_traceback", [True, False])
async def test_error_regression_async_def(
    caplog: pytest.LogCaptureFixture, logger: logging.Logger | None, log_traceback: bool
):
    @log_decorator(logger, log_traceback=log_traceback)
    async def _raising_error() -> None:
        raise RuntimeError("Raising as expected")

    caplog.clear()

    await logged_gather(_raising_error(), reraise=False)

    if log_traceback:
        assert "Traceback" in caplog.text
    else:
        assert "Traceback" not in caplog.text


@pytest.mark.parametrize("logger", [None, _logger])
@pytest.mark.parametrize("log_traceback", [True, False])
async def test_error_regression_def(
    caplog: pytest.LogCaptureFixture, logger: logging.Logger | None, log_traceback: bool
):
    @log_decorator(logger, log_traceback=log_traceback)
    def _raising_error() -> None:
        raise RuntimeError("Raising as expected")

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


@pytest.mark.parametrize("with_log_duration", [True, False])
def test_log_context_with_log_duration(
    caplog: pytest.LogCaptureFixture, with_log_duration: bool
):
    caplog.clear()

    with log_context(_logger, logging.INFO, "test", log_duration=with_log_duration):
        ...

    assert "Starting test ..." in caplog.text
    if with_log_duration:
        assert "Finished test in " in caplog.text
    else:
        assert "Finished test" in caplog.text


@pytest.mark.parametrize(
    "msg, args, extra",
    [
        ("nothing", (), None),
        ("format %s", ("this_arg",), None),
        ("only extra", (), {"only": "extra"}),
        ("format %s", ("this_arg",), {"me": "he"}),
    ],
)
def test_log_context(
    caplog: pytest.LogCaptureFixture,
    msg: str,
    args: tuple[Any, ...],
    extra: dict[str, Any] | None,
):
    caplog.clear()

    with log_context(_logger, logging.INFO, msg, *args, extra=extra):
        ...
    assert len(caplog.messages) == 2

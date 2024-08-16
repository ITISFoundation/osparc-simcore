# pylint:disable=redefined-outer-name

import logging
from typing import Any

import pytest
from faker import Faker
from servicelib.logging_utils import (
    LogExtra,
    LogLevelInt,
    LogMessageStr,
    guess_message_log_level,
    log_context,
    log_decorator,
)

_logger = logging.getLogger(__name__)


@pytest.mark.parametrize("logger", [None, _logger])
async def test_error_regression_async_def(
    caplog: pytest.LogCaptureFixture, logger: logging.Logger | None, faker: Faker
):
    @log_decorator(logger, logging.INFO)
    async def _not_raising_fct(
        argument1: int, argument2: str, *, keyword_arg1: bool, keyword_arg2: str
    ) -> int:
        assert argument1 is not None
        assert argument2 is not None
        assert keyword_arg1 is not None
        assert keyword_arg2 is not None
        return 0

    @log_decorator(logger, logging.INFO)
    async def _raising_error(
        argument1: int, argument2: str, *, keyword_arg1: bool, keyword_arg2: str
    ) -> None:
        assert argument1 is not None
        assert argument2 is not None
        assert keyword_arg1 is not None
        assert keyword_arg2 is not None
        msg = "Raising as expected"
        raise RuntimeError(msg)

    caplog.clear()
    argument1 = faker.pyint()
    argument2 = faker.pystr()
    key_argument1 = faker.pybool()
    key_argument2 = faker.pystr()

    result = await _not_raising_fct(
        argument1, argument2, keyword_arg1=key_argument1, keyword_arg2=key_argument2
    )
    assert result == 0
    assert len(caplog.records) == 2
    info_record = caplog.records[0]
    assert info_record.levelno == logging.INFO
    assert (
        f"{_not_raising_fct.__module__.split('.')[-1]}:{_not_raising_fct.__name__}({argument1!r}, {argument2!r}, keyword_arg1={key_argument1!r}, keyword_arg2={key_argument2!r})"
        in info_record.message
    )
    return_record = caplog.records[1]
    assert return_record.levelno == logging.INFO
    assert not return_record.exc_text
    assert (
        f"{_not_raising_fct.__module__.split('.')[-1]}:{_not_raising_fct.__name__} returned {result!r}"
        in return_record.message
    )

    caplog.clear()
    with pytest.raises(RuntimeError):
        await _raising_error(
            argument1, argument2, keyword_arg1=key_argument1, keyword_arg2=key_argument2
        )

    assert len(caplog.records) == 2
    info_record = caplog.records[0]
    assert info_record.levelno == logging.INFO
    assert (
        f"{_raising_error.__module__.split('.')[-1]}:{_raising_error.__name__}({argument1!r}, {argument2!r}, keyword_arg1={key_argument1!r}, keyword_arg2={key_argument2!r})"
        in info_record.message
    )
    error_record = caplog.records[1]
    assert error_record.levelno == logging.ERROR
    assert error_record.exc_text
    assert "Traceback" in error_record.exc_text


@pytest.mark.parametrize("logger", [None, _logger])
def test_error_regression_sync_def(
    caplog: pytest.LogCaptureFixture, logger: logging.Logger | None, faker: Faker
):
    @log_decorator(logger, logging.INFO)
    def _not_raising_fct(
        argument1: int, argument2: str, *, keyword_arg1: bool, keyword_arg2: str
    ) -> int:
        assert argument1 is not None
        assert argument2 is not None
        assert keyword_arg1 is not None
        assert keyword_arg2 is not None
        return 0

    @log_decorator(logger, logging.INFO)
    def _raising_error(
        argument1: int, argument2: str, *, keyword_arg1: bool, keyword_arg2: str
    ) -> None:
        assert argument1 is not None
        assert argument2 is not None
        assert keyword_arg1 is not None
        assert keyword_arg2 is not None
        msg = "Raising as expected"
        raise RuntimeError(msg)

    caplog.clear()
    argument1 = faker.pyint()
    argument2 = faker.pystr()
    key_argument1 = faker.pybool()
    key_argument2 = faker.pystr()

    result = _not_raising_fct(
        argument1, argument2, keyword_arg1=key_argument1, keyword_arg2=key_argument2
    )
    assert result == 0
    assert len(caplog.records) == 2
    info_record = caplog.records[0]
    assert info_record.levelno == logging.INFO
    assert (
        f"{_not_raising_fct.__module__.split('.')[-1]}:{_not_raising_fct.__name__}({argument1!r}, {argument2!r}, keyword_arg1={key_argument1!r}, keyword_arg2={key_argument2!r})"
        in info_record.message
    )
    return_record = caplog.records[1]
    assert return_record.levelno == logging.INFO
    assert not return_record.exc_text
    assert (
        f"{_not_raising_fct.__module__.split('.')[-1]}:{_not_raising_fct.__name__} returned {result!r}"
        in return_record.message
    )

    caplog.clear()
    with pytest.raises(RuntimeError):
        _raising_error(
            argument1, argument2, keyword_arg1=key_argument1, keyword_arg2=key_argument2
        )

    assert len(caplog.records) == 2
    info_record = caplog.records[0]
    assert info_record.levelno == logging.INFO
    assert (
        f"{_raising_error.__module__.split('.')[-1]}:{_raising_error.__name__}({argument1!r}, {argument2!r}, keyword_arg1={key_argument1!r}, keyword_arg2={key_argument2!r})"
        in info_record.message
    )
    error_record = caplog.records[1]
    assert error_record.levelno == logging.ERROR
    assert error_record.exc_text
    assert "Traceback" in error_record.exc_text


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

    with log_context(_logger, logging.ERROR, "test", log_duration=with_log_duration):
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
    extra: LogExtra | None,
):
    caplog.clear()

    with log_context(_logger, logging.ERROR, msg, *args, extra=extra):
        ...
    assert len(caplog.messages) == 2

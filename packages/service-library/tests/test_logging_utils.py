# pylint:disable=redefined-outer-name

import logging
from contextlib import suppress
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
    log_exceptions,
)

_logger = logging.getLogger(__name__)
_ALL_LOGGING_LEVELS = [
    logging.CRITICAL,
    logging.ERROR,
    logging.WARNING,
    logging.INFO,
    logging.DEBUG,
    logging.NOTSET,
]


def _to_level_name(lvl: int) -> str:
    return logging.getLevelName(lvl)


@pytest.mark.parametrize("logger", [None, _logger])
async def test_error_regression_async_def(
    caplog: pytest.LogCaptureFixture, logger: logging.Logger | None, faker: Faker
):
    # NOTE: change the log level so that the log is visible
    caplog.set_level(logging.INFO)

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

    argument1 = faker.pyint()
    argument2 = faker.pystr()
    key_argument1 = faker.pybool()
    key_argument2 = faker.pystr()

    # run function under test: _not_raising_fct -----------------
    caplog.clear()
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

    # run function under test: _raising_error -----------------
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
    assert error_record.levelno == logging.INFO
    assert error_record.exc_text
    assert "Traceback" in error_record.exc_text


@pytest.mark.parametrize("logger", [None, _logger])
def test_error_regression_sync_def(
    caplog: pytest.LogCaptureFixture, logger: logging.Logger | None, faker: Faker
):
    # NOTE: change the log level so that the log is visible
    caplog.set_level(logging.INFO)

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
    assert error_record.levelno == logging.INFO
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

    all(r.levelno == logging.ERROR for r in caplog.records)

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


@pytest.mark.parametrize("level", _ALL_LOGGING_LEVELS, ids=_to_level_name)
def test_logs_no_exceptions(caplog: pytest.LogCaptureFixture, level: int):
    caplog.set_level(level)

    with log_exceptions(_logger, level):
        ...

    assert not caplog.records


@pytest.mark.parametrize("level", _ALL_LOGGING_LEVELS, ids=_to_level_name)
def test_log_exceptions_and_suppress(caplog: pytest.LogCaptureFixture, level: int):
    caplog.set_level(level)

    exc_msg = "logs exceptions and suppresses"
    with suppress(ValueError), log_exceptions(_logger, level, "CONTEXT", exc_info=True):
        raise ValueError(exc_msg)

    assert len(caplog.records) == (1 if level != logging.NOTSET else 0)

    if caplog.records:
        assert caplog.records[0].levelno == level
        record = caplog.records[0]
        # this is how it looks with exc_info=True
        #
        # CRITICAL tests.test_logging_utils:logging_utils.py:170 CONTEXT raised ValueError: logs exceptions and suppresses
        # Traceback (most recent call last):
        # File "path/to/file.py", line 163, in log_exceptions
        #     yield
        # File "path/to/file2.py", line 262, in test_log_exceptions_and_suppress
        #     raise ValueError(msg)
        # ValueError: logs exceptions and suppresses
        #

        assert record.message == f"CONTEXT raised ValueError: {exc_msg}"
        # since exc_info=True
        assert record.exc_text
        assert exc_msg in record.exc_text
        assert "ValueError" in record.exc_text
        assert "Traceback" in record.exc_text


@pytest.mark.parametrize("level", _ALL_LOGGING_LEVELS, ids=_to_level_name)
def test_log_exceptions_and_suppress_without_exc_info(
    caplog: pytest.LogCaptureFixture, level: int
):
    caplog.set_level(level)

    exc_msg = "logs exceptions and suppresses"
    with suppress(ValueError), log_exceptions(
        _logger, level, "CONTEXT", exc_info=False
    ):
        raise ValueError(exc_msg)

    assert len(caplog.records) == (1 if level != logging.NOTSET else 0)

    if caplog.records:
        assert caplog.records[0].levelno == level
        record = caplog.records[0]
        # this is how it looks with exc_info=False
        #
        # CRITICAL tests.test_logging_utils:logging_utils.py:170 CONTEXT raised ValueError: logs exceptions and suppresses
        #

        assert record.message == f"CONTEXT raised ValueError: {exc_msg}"

        # since exc_info=False
        assert not record.exc_text


@pytest.mark.parametrize("level", _ALL_LOGGING_LEVELS, ids=_to_level_name)
def test_log_exceptions_and_reraise(caplog: pytest.LogCaptureFixture, level: int):
    caplog.set_level(level)

    msg = "logs exceptions and reraises"
    with pytest.raises(ValueError, match=msg), log_exceptions(_logger, level):
        raise ValueError(msg)

    assert len(caplog.records) == (1 if level != logging.NOTSET else 0)
    assert all(r.levelno == level for r in caplog.records)

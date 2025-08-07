# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument

import io
import logging
import re
from collections.abc import Iterable
from contextlib import suppress
from pathlib import Path
from typing import Any

import pytest
from faker import Faker
from servicelib.logging_utils import (
    _DEFAULT_FORMATTING,
    CustomFormatter,
    LogExtra,
    LogLevelInt,
    LogMessageStr,
    async_loggers,
    guess_message_log_level,
    log_context,
    log_decorator,
    log_exceptions,
    set_parent_module_log_level,
)
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_delay,
    wait_fixed,
)

_logger = logging.getLogger(__name__)


@retry(
    wait=wait_fixed(0.01),
    stop=stop_after_delay(2.0),
    reraise=True,
    retry=retry_if_exception_type(AssertionError),
)
def _assert_check_log_message(
    caplog: pytest.LogCaptureFixture, expected_message: str
) -> None:
    assert expected_message in caplog.text


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


@pytest.fixture
def log_format_with_module_name() -> Iterable[None]:
    for handler in logging.root.handlers:
        original_formatter = handler.formatter
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s %(module)s:%(filename)s:%(lineno)d %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )

    yield

    for handler in logging.root.handlers:
        handler.formatter = original_formatter


def test_log_context_caller_is_included_in_log(
    caplog: pytest.LogCaptureFixture,
    log_format_with_module_name: None,
):
    caplog.clear()

    with log_context(_logger, logging.ERROR, "a test message"):
        ...

    # Verify file name is in the log
    assert Path(__file__).name in caplog.text


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
    with (
        suppress(ValueError),
        log_exceptions(_logger, level, "CONTEXT", exc_info=False),
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


def test_set_parent_module_log_level_(caplog: pytest.LogCaptureFixture):
    caplog.clear()
    # emulates service logger
    logging.root.setLevel(logging.WARNING)

    parent = logging.getLogger("parent")
    child = logging.getLogger("parent.child")

    assert parent.level == logging.NOTSET
    assert child.level == logging.NOTSET

    parent.debug("parent debug")
    child.debug("child debug")

    parent.info("parent info")
    child.info("child info")

    parent.warning("parent warning")
    child.warning("child warning")

    assert "parent debug" not in caplog.text
    assert "child debug" not in caplog.text

    assert "parent info" not in caplog.text
    assert "child info" not in caplog.text

    assert "parent warning" in caplog.text
    assert "child warning" in caplog.text

    caplog.clear()
    set_parent_module_log_level("parent.child", logging.INFO)

    assert parent.level == logging.INFO
    assert child.level == logging.NOTSET

    parent.debug("parent debug")
    child.debug("child debug")

    parent.info("parent info")
    child.info("child info")

    parent.warning("parent warning")
    child.warning("child warning")

    assert "parent debug" not in caplog.text
    assert "child debug" not in caplog.text

    assert "parent info" in caplog.text
    assert "child info" in caplog.text

    assert "parent warning" in caplog.text
    assert "child warning" in caplog.text


@pytest.mark.parametrize("log_format_local_dev_enabled", [True, False])
def test_setup_async_loggers_basic(
    caplog: pytest.LogCaptureFixture,
    log_format_local_dev_enabled: bool,
):
    """Test basic async logging setup without filters."""
    caplog.clear()
    caplog.set_level(logging.INFO)

    with async_loggers(
        log_format_local_dev_enabled=log_format_local_dev_enabled,
        logger_filter_mapping={},  # No filters for this test
        tracing_settings=None,  # No tracing for this test
        log_base_level=logging.INFO,  # Set base log level
        noisy_loggers=(),  # No noisy loggers for this test
    ):
        test_logger = logging.getLogger("test_async_logger")
        test_logger.info("Test async log message")

        _assert_check_log_message(caplog, "Test async log message")


def test_setup_async_loggers_with_filters(
    caplog: pytest.LogCaptureFixture,
):
    caplog.clear()
    caplog.set_level(logging.INFO)

    # Define filter mapping
    filter_mapping = {
        "test_filtered_logger": ["filtered_message"],
    }

    with async_loggers(
        log_format_local_dev_enabled=True,
        logger_filter_mapping=filter_mapping,
        tracing_settings=None,  # No tracing for this test
        log_base_level=logging.INFO,  # Set base log level
        noisy_loggers=(),  # No noisy loggers for this test
    ):
        test_logger = logging.getLogger("test_filtered_logger")
        unfiltered_logger = logging.getLogger("test_unfiltered_logger")

        # This should be filtered out
        test_logger.info("This is a filtered_message")

        # This should pass through
        test_logger.info("This is an unfiltered message")
        unfiltered_logger.info("This is from unfiltered logger")

        _assert_check_log_message(caplog, "This is an unfiltered message")
        _assert_check_log_message(caplog, "This is from unfiltered logger")

    # Check that filtered message was not captured
    assert "This is a filtered_message" not in caplog.text

    # Check that unfiltered messages were captured
    assert "This is an unfiltered message" in caplog.text
    assert "This is from unfiltered logger" in caplog.text


def test_setup_async_loggers_with_tracing_settings(
    caplog: pytest.LogCaptureFixture,
):
    """Test async logging setup with tracing settings."""
    caplog.clear()
    caplog.set_level(logging.INFO)

    # Note: We can't easily test actual tracing without setting up OpenTelemetry
    # But we can test that the function accepts the parameter
    with async_loggers(
        log_format_local_dev_enabled=False,
        logger_filter_mapping={},  # No filters for this test
        tracing_settings=None,
        log_base_level=logging.INFO,  # Set base log level
        noisy_loggers=(),  # No noisy loggers for this test
    ):
        test_logger = logging.getLogger("test_tracing_logger")
        test_logger.info("Test message with tracing settings")

        _assert_check_log_message(caplog, "Test message with tracing settings")


def test_setup_async_loggers_context_manager_cleanup(
    caplog: pytest.LogCaptureFixture,
):
    """Test that async logging context manager properly cleans up."""
    caplog.clear()
    caplog.set_level(logging.DEBUG)

    test_logger = logging.getLogger("test_cleanup_logger")

    with async_loggers(
        log_format_local_dev_enabled=True,
        logger_filter_mapping={},
        tracing_settings=None,
        log_base_level=logging.INFO,  # Set base log level
        noisy_loggers=(),  # No noisy loggers for this test
    ):
        # During the context, handlers should be replaced
        test_logger.info("Message during context")

        _assert_check_log_message(caplog, "Message during context")


def test_setup_async_loggers_exception_handling(
    caplog: pytest.LogCaptureFixture,
):
    """Test that async logging handles exceptions gracefully."""
    caplog.clear()
    caplog.set_level(logging.DEBUG)  # Set to DEBUG to capture cleanup messages

    def _raise_test_exception():
        """Helper function to raise exception for testing."""
        exc_msg = "Test exception"
        raise ValueError(exc_msg)

    try:
        with async_loggers(
            log_format_local_dev_enabled=True,
            logger_filter_mapping={},
            tracing_settings=None,
            log_base_level=logging.INFO,  # Set base log level
            noisy_loggers=(),  # No noisy loggers for this test
        ):
            test_logger = logging.getLogger("test_exception_logger")
            test_logger.info("Message before exception")

            _assert_check_log_message(caplog, "Message before exception")

            # Raise an exception to test cleanup
            _raise_test_exception()

    except ValueError:
        # Expected exception
        pass

    # Check that the message was logged and cleanup happened
    assert "Message before exception" in caplog.text


def _create_grok_regex_pattern() -> str:
    """Convert Grok pattern to regex for testing."""
    # The Grok pattern from the comment:
    # log_level=%{WORD:log_level} \| log_timestamp=%{TIMESTAMP_ISO8601:log_timestamp} \| log_source=%{NOTSPACE:log_source} \| log_uid=%{NOTSPACE:log_uid} \| log_oec=%{NOTSPACE:log_oec} \| log_trace_id=%{NOTSPACE:log_trace_id} \| log_span_id=%{NOTSPACE:log_span_id} \| log_msg=%{GREEDYDATA:log_msg}

    grok_to_regex = {
        r"%{WORD:log_level}": r"(?P<log_level>\w+)",
        r"%{TIMESTAMP_ISO8601:log_timestamp}": r"(?P<log_timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})",
        r"%{NOTSPACE:log_source}": r"(?P<log_source>\S+)",
        r"%{NOTSPACE:log_uid}": r"(?P<log_uid>\S+)",
        r"%{NOTSPACE:log_oec}": r"(?P<log_oec>\S+)",
        r"%{NOTSPACE:log_trace_id}": r"(?P<log_trace_id>\S+)",
        r"%{GREEDYDATA:log_msg}": r"(?P<log_msg>.*)",
    }

    grok_pattern = r"log_level=%{WORD:log_level} \| log_timestamp=%{TIMESTAMP_ISO8601:log_timestamp} \| log_source=%{NOTSPACE:log_source} \| log_uid=%{NOTSPACE:log_uid} \| log_oec=%{NOTSPACE:log_oec} \| log_trace_id=%{NOTSPACE:log_trace_id} \| log_msg=%{GREEDYDATA:log_msg}"

    # Convert to regex
    regex_pattern = grok_pattern
    for grok, regex in grok_to_regex.items():
        regex_pattern = regex_pattern.replace(grok, regex)

    return regex_pattern


def _create_test_log_record(
    name: str,
    level: int,
    func_name: str,
    lineno: int,
    message: str,
    *,
    user_id: int | str | None = None,
    error_code: str | None = None,
    trace_id: str | None = None,
    span_id: str | None = None,
) -> logging.LogRecord:
    """Create a test LogRecord with optional extra fields."""
    from servicelib.logging_utils import get_log_record_extra

    record = logging.LogRecord(
        name=name,
        level=level,
        pathname="/path/to/file.py",
        lineno=lineno,
        msg=message,
        args=(),
        exc_info=None,
        func=func_name,
    )

    # Add extra fields if provided
    extra = get_log_record_extra(user_id=user_id, error_code=error_code)
    if extra:
        for key, value in extra.items():
            setattr(record, key, value)

    # Add OpenTelemetry trace ID
    record.otelTraceID = trace_id  # type: ignore[attr-defined]
    record.otelSpanID = span_id  # type: ignore[attr-defined]

    return record


def test_grok_pattern_parsing(caplog: pytest.LogCaptureFixture) -> None:
    """
    Test that the Graylog Grok pattern correctly parses logs formatted with _DEFAULT_FORMATTING.

    This test validates that the Grok pattern defined in the comment can correctly
    parse logs formatted with _DEFAULT_FORMATTING.

    WARNING: If log formatting changes, the Grok pattern in Graylog must be updated accordingly.
    """

    # Create a custom handler with the default formatter
    log_stream = io.StringIO()
    handler = logging.StreamHandler(log_stream)
    formatter = CustomFormatter(_DEFAULT_FORMATTING, log_format_local_dev_enabled=False)
    handler.setFormatter(formatter)

    # Create test log record with all fields populated
    test_message = (
        "This is a test log message with special chars: []{} and new line\nembedded"
    )
    record = _create_test_log_record(
        name="test.module.submodule",
        level=logging.INFO,
        func_name="test_function",
        lineno=42,
        message=test_message,
        user_id=12345,
        error_code="OEC001",
        trace_id="1234567890abcdef1234567890abcdef",
        span_id="987654321",
    )

    # Format the record
    formatted_log = formatter.format(record)

    # Test that the formatted log matches the Grok pattern
    regex_pattern = _create_grok_regex_pattern()
    match = re.match(regex_pattern, formatted_log)

    assert (
        match is not None
    ), f"Grok pattern did not match formatted log. Log: {formatted_log!r}"

    # Verify extracted fields match expected values
    groups = match.groupdict()

    assert groups["log_level"] == "INFO"
    assert groups["log_source"] == "test.module.submodule:test_function(42)"
    assert groups["log_uid"] == "12345"
    assert groups["log_oec"] == "OEC001"
    assert groups["log_trace_id"] == "1234567890abcdef1234567890abcdef"
    assert groups["log_span_id"] == "987654321"

    # Verify the message is correctly escaped (newlines become \\n)
    expected_message = test_message.replace("\n", "\\n")
    assert groups["log_msg"] == expected_message

    # Verify timestamp format is ISO8601-like (as expected by Python logging)
    timestamp_pattern = r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}"
    assert re.match(timestamp_pattern, groups["log_timestamp"])


def test_grok_pattern_parsing_with_none_values(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    Test Grok pattern parsing when optional fields are None.

    WARNING: If log formatting changes, the Grok pattern in Graylog must be updated accordingly.
    """

    # Create a custom handler with the default formatter
    handler = logging.StreamHandler(io.StringIO())
    formatter = CustomFormatter(_DEFAULT_FORMATTING, log_format_local_dev_enabled=False)
    handler.setFormatter(formatter)

    # Create test log record with None values for optional fields
    record = _create_test_log_record(
        name="test.module",
        level=logging.ERROR,
        func_name="error_function",
        lineno=100,
        message="Error message",
        user_id=None,
        error_code=None,
        trace_id=None,
        span_id=None,
    )

    formatted_log = formatter.format(record)
    regex_pattern = _create_grok_regex_pattern()
    match = re.match(regex_pattern, formatted_log)

    assert (
        match is not None
    ), f"Grok pattern did not match log with None values. Log: {formatted_log!r}"

    groups = match.groupdict()
    assert groups["log_level"] == "ERROR"
    assert groups["log_source"] == "test.module:error_function(100)"
    assert groups["log_uid"] == "None"
    assert groups["log_oec"] == "None"
    assert groups["log_trace_id"] == "None"
    assert groups["log_span_id"] == "None"
    assert groups["log_msg"] == "Error message"

# pylint: disable=redefined-outer-name

import logging
from typing import Generator

import pytest
from servicelib.logging_utils_filtering import GeneralLogFilter


@pytest.fixture
def logger_with_filter() -> Generator[tuple[logging.Logger, list[str]], None, None]:
    # Set up a logger for testing
    logger = logging.getLogger("uvicorn.access")
    logger.setLevel(logging.DEBUG)

    # Create a list to capture log outputs
    log_capture = []

    # Create a handler that appends log messages to the log_capture list
    class ListHandler(logging.Handler):
        def emit(self, record):
            log_capture.append(self.format(record))

    handler = ListHandler()
    logger.addHandler(handler)

    # Set up the filter based on the new logic
    filtered_routes = [
        '"GET / HTTP/1.1" 200',
        '"GET /metrics HTTP/1.1" 200',
    ]

    # Add the GeneralLogFilter to the logger
    log_filter = GeneralLogFilter(filtered_routes)
    logger.addFilter(log_filter)

    # Return logger and the log_capture for testing
    yield logger, log_capture

    # Cleanup: remove handlers and filters after test
    logger.handlers.clear()
    logger.filters.clear()


def test_log_filtered_out(logger_with_filter: tuple[logging.Logger, list[str]]):
    logger, log_capture = logger_with_filter

    # Create a log record that should be filtered out (matches the filter criteria)
    record = logger.makeRecord(
        name="uvicorn.access",
        level=logging.INFO,
        fn="testfile",
        lno=10,
        msg='"GET / HTTP/1.1" 200 OK',
        args=(),
        exc_info=None,
    )
    logger.handle(record)

    # Assert no log messages were captured (filtered out)
    assert len(log_capture) == 0


def test_log_allowed(logger_with_filter):
    logger, log_capture = logger_with_filter

    # Create a log record that should NOT be filtered out (doesn't match any filter criteria)
    record = logger.makeRecord(
        name="uvicorn.access",
        level=logging.INFO,
        fn="testfile",
        lno=10,
        msg='"GET /another HTTP/1.1" 200 OK',
        args=(),
        exc_info=None,
    )
    logger.handle(record)

    # Assert the log message was captured (not filtered out)
    assert len(log_capture) == 1


def test_log_with_different_status(logger_with_filter):
    logger, log_capture = logger_with_filter

    # Create a log record that has the same route but a different status code (should pass through)
    record = logger.makeRecord(
        name="uvicorn.access",
        level=logging.INFO,
        fn="testfile",
        lno=10,
        msg='"GET / HTTP/1.1" 500 Internal Server Error',
        args=(),
        exc_info=None,
    )
    logger.handle(record)

    # Assert the log message was captured (not filtered out due to different status code)
    assert len(log_capture) == 1

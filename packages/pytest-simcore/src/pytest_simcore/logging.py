# In conftest.py or test_logging_utils.py
import contextlib
import logging
from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from pytest_mock import MockerFixture
from servicelib.logging_utils import async_loggers


@pytest.fixture(autouse=True)
def preserve_caplog_for_async_logging(mocker: MockerFixture) -> None:
    # Patch async_loggers to preserve caplog handlers,
    # and pytest logs in general as pytest captures logs in a special way
    # that is not compatible with the queue handler used in async logging.
    original_setup = async_loggers

    @contextmanager
    def patched_async_loggers(**kwargs) -> Iterator[None]:
        # Find caplog's handler in root logger
        root_logger = logging.getLogger()
        caplog_handlers = [
            h for h in root_logger.handlers if "LogCaptureHandler" in f"{type(h)}"
        ]

        with original_setup(**kwargs):
            # After setup, restore caplog handlers alongside queue handler
            for handler in caplog_handlers:
                if handler not in root_logger.handlers:
                    root_logger.addHandler(handler)
            yield

    methods_to_patch = [
        "servicelib.logging_utils.async_loggers",
        "servicelib.fastapi.logging_lifespan.async_loggers",
        "tests.test_logging_utils.async_loggers",
    ]
    for method in methods_to_patch:
        with contextlib.suppress(AttributeError, ModuleNotFoundError):
            # Patch the method to use our patched version
            mocker.patch(method, patched_async_loggers)

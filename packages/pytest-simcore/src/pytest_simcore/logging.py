# In conftest.py or test_logging_utils.py
import contextlib
import logging
from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from pytest_mock import MockerFixture
from servicelib.logging_utils import setup_async_loggers_lifespan


@pytest.fixture(autouse=True)
def preserve_caplog_for_async_logging(
    request: pytest.FixtureRequest, mocker: MockerFixture
) -> None:
    # Patch setup_async_loggers_lifespan to preserve caplog handlers
    original_setup = setup_async_loggers_lifespan

    @contextmanager
    def patched_setup_async_loggers_lifespan(**kwargs) -> Iterator[None]:
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
        "servicelib.logging_utils.setup_async_loggers_lifespan",
        "servicelib.fastapi.logging_lifespan.setup_async_loggers_lifespan",
        "tests.test_logging_utils.setup_async_loggers_lifespan",
    ]
    for method in methods_to_patch:
        with contextlib.suppress(AttributeError, ModuleNotFoundError):
            # Patch the method to use our patched version
            mocker.patch(method, patched_setup_async_loggers_lifespan)

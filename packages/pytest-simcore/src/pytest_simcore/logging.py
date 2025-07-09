# In conftest.py or test_logging_utils.py
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from unittest.mock import patch

import pytest
from servicelib.logging_utils import setup_async_loggers_lifespan


@pytest.fixture(autouse=True)
def preserve_caplog_for_async_logging(request):
    """Automatically preserve caplog handlers when both caplog and async logging are used."""
    # Check if this test uses caplog fixture
    if "caplog" not in request.fixturenames:
        yield  # No caplog, no patching needed
        return

    # Patch setup_async_loggers_lifespan to preserve caplog handlers
    original_setup = setup_async_loggers_lifespan

    @asynccontextmanager
    async def patched_setup_async_loggers_lifespan(**kwargs) -> AsyncIterator[None]:
        # Find caplog's handler in root logger
        root_logger = logging.getLogger()
        caplog_handlers = [
            h for h in root_logger.handlers if "LogCaptureHandler" in f"{type(h)}"
        ]

        async with original_setup(**kwargs):
            # After setup, restore caplog handlers alongside queue handler
            for handler in caplog_handlers:
                if handler not in root_logger.handlers:
                    root_logger.addHandler(handler)
            yield

    with (
        patch(
            "tests.test_logging_utils.setup_async_loggers_lifespan",
            patched_setup_async_loggers_lifespan,
        ),
        patch(
            "servicelib.logging_utils.setup_async_loggers_lifespan",
            patched_setup_async_loggers_lifespan,
        ),
    ):
        yield

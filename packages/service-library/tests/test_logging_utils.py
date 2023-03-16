# pylint:disable=redefined-outer-name

import logging
from typing import Optional

import pytest
from pytest import LogCaptureFixture
from servicelib.logging_utils import log_decorator
from servicelib.utils import logged_gather

logger = logging.getLogger(__name__)


@pytest.mark.parametrize("logger", [None, logger])
@pytest.mark.parametrize("log_traceback", [True, False])
async def test_error_regression(
    caplog: LogCaptureFixture, logger: Optional[logging.Logger], log_traceback: bool
):
    caplog.clear()

    @log_decorator(logger, log_traceback=log_traceback)
    async def _raising_error() -> None:
        raise RuntimeError("Raising as expected")

    await logged_gather(_raising_error(), reraise=False)

    if log_traceback:
        assert "Traceback" in caplog.text
    else:
        assert "Traceback" not in caplog.text

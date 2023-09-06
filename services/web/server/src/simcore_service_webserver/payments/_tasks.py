import asyncio
import json
import logging
import random
from collections.abc import AsyncIterator
from typing import Any

from aiohttp import web
from models_library.api_schemas_webserver.wallets import PaymentID
from servicelib.aiohttp.typing_extension import CleanupContextFunc
from tenacity import retry
from tenacity.before_sleep import before_sleep_log
from tenacity.wait import wait_exponential

from ._api import complete_payment
from ._db import get_pending_payment_transactions_ids

_logger = logging.getLogger(__name__)


_PERIODIC_TASK_NAME = f"{__name__}.fake_payment_completion"
_APP_TASK_KEY = f"{_PERIODIC_TASK_NAME}.task"


async def _fake_payment_completion(app: web.Application, payment_id: PaymentID):
    # Fakes processing time
    await asyncio.sleep(random.uniform(0.5, 2))  # nosec # noqa: S311 # NOSONAR

    # Three different possible outcomes
    possible_outcomes = [
        # 1. Accepted
        {"app": app, "payment_id": payment_id, "success": True},
        # 2. Rejected
        {
            "app": app,
            "payment_id": payment_id,
            "success": False,
            "message": "Payment rejected",
        },
        # 3. does not complete ever ???
    ]
    kwargs: dict[str, Any] = random.choice(possible_outcomes)  # noqa: S311

    _logger.info("Faking payment completion as %s", json.dumps(kwargs, indent=1))
    await complete_payment(**kwargs)


@retry(
    wait=wait_exponential(min=5, max=30),
    before_sleep=before_sleep_log(_logger, logging.WARNING),
)
async def _run_resilient_task(app: web.Application):
    """NOTE: Resilient task: if fails, it tries foreever"""
    pending = await get_pending_payment_transactions_ids(app)
    _logger.debug("Pending transactions: %s", pending)
    if pending:
        asyncio.gather(
            *[_fake_payment_completion(app, payment_id) for payment_id in pending]
        )


async def _run_periodically(app: web.Application, wait_period_s: float):
    while True:
        await _run_resilient_task(app)
        await asyncio.sleep(wait_period_s)


def create_background_task_to_fake_payment_completion(
    wait_period_s: float,
) -> CleanupContextFunc:
    async def _cleanup_ctx_fun(
        app: web.Application,
    ) -> AsyncIterator[None]:
        # setup
        task = asyncio.create_task(
            _run_periodically(app, wait_period_s),
            name=_PERIODIC_TASK_NAME,
        )
        app[_APP_TASK_KEY] = task

        yield

        # tear-down
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            assert task.cancelled()  # nosec

    return _cleanup_ctx_fun

# pylint: disable=redefined-outer-name

from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from faker import Faker
from fastapi import FastAPI
from models_library.rabbitmq_messages import (
    CreditsLimit,
    WalletCreditsLimitReachedMessage,
)
from simcore_service_director_v2.modules.rabbitmq import handler_out_of_credits


@pytest.fixture(params=[True, False])
def ignore_limits(request: pytest.FixtureRequest) -> bool:
    return request.param


@pytest.fixture
async def mock_app(ignore_limits: bool) -> FastAPI:
    mock = AsyncMock()
    mock.state.settings.DYNAMIC_SERVICES.DYNAMIC_SCHEDULER.DIRECTOR_V2_DYNAMIC_SCHEDULER_CLOSE_SERVICES_VIA_FRONTEND_WHEN_CREDITS_LIMIT_REACHED = (
        ignore_limits
    )
    mock.state.dynamic_sidecar_scheduler = AsyncMock()
    return mock


@pytest.fixture
def message(faker: Faker) -> WalletCreditsLimitReachedMessage:
    return WalletCreditsLimitReachedMessage(
        service_run_id=faker.pystr(),
        user_id=faker.pyint(),
        project_id=faker.uuid4(cast_to=None),
        node_id=faker.uuid4(cast_to=None),
        wallet_id=faker.pyint(),
        credits=Decimal(-10),
        credits_limit=CreditsLimit(0),
    )


async def test_handler_out_of_credits(
    mock_app: FastAPI, message: WalletCreditsLimitReachedMessage, ignore_limits
):
    await handler_out_of_credits(mock_app, message.model_dump_json().encode())

    removal_mark_count = (
        mock_app.state.dynamic_sidecar_scheduler.mark_all_services_in_wallet_for_removal.call_count
    )
    assert removal_mark_count == 0 if ignore_limits else 1

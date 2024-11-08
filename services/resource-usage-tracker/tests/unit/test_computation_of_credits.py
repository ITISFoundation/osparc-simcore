# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from simcore_service_resource_usage_tracker.services.utils import (
    compute_service_run_credit_costs,
)


@pytest.mark.parametrize(
    "stop,start,cost_per_unit,expected_cost",
    [
        (
            datetime.now(tz=timezone.utc),
            datetime.now(tz=timezone.utc) - timedelta(days=1),
            Decimal(25),
            Decimal(600),
        ),
        (
            datetime.now(tz=timezone.utc),
            datetime.now(tz=timezone.utc) - timedelta(days=2.5),
            Decimal(40),
            Decimal(2400),
        ),
        (
            datetime.now(tz=timezone.utc),
            datetime.now(tz=timezone.utc) - timedelta(days=25),
            Decimal(12),
            Decimal(7200),
        ),
        (
            datetime.now(tz=timezone.utc),
            datetime.now(tz=timezone.utc) - timedelta(days=45),
            Decimal(13.5),
            Decimal(14580),
        ),
        (
            datetime.now(tz=timezone.utc),
            datetime.now(tz=timezone.utc) - timedelta(minutes=37),
            Decimal(25),
            round(Decimal(15.42), 2),
        ),
    ],
)
async def test_credit_computation(stop, start, cost_per_unit, expected_cost):
    computed_credits = await compute_service_run_credit_costs(
        start, stop, cost_per_unit
    )
    assert computed_credits == expected_cost


async def test_invalid_dates_in_credit_computation():
    start = datetime.now(tz=timezone.utc)
    stop = datetime.now(tz=timezone.utc) - timedelta(minutes=3)
    cost_per_unit = Decimal(25)

    with pytest.raises(ValueError):
        await compute_service_run_credit_costs(start, stop, cost_per_unit)

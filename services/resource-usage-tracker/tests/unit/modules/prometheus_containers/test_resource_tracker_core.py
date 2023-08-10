from datetime import datetime, timedelta, timezone

import pytest
from simcore_service_resource_usage_tracker.modules.prometheus_containers.core import (
    _prepare_prom_query_parameters,
    _PromQueryParameters,
)

_current_timestamp = datetime.now(tz=timezone.utc)


@pytest.mark.parametrize(
    "prometheus_last_scraped_timestamp,current_timestamp,expected",
    [
        (
            _current_timestamp - timedelta(minutes=1),
            _current_timestamp,
            1,
        ),
        (
            _current_timestamp - timedelta(minutes=24),
            _current_timestamp,
            1,
        ),
        (
            _current_timestamp - timedelta(minutes=49),
            _current_timestamp,
            2,
        ),
        (
            _current_timestamp - timedelta(minutes=300),
            _current_timestamp,
            12,
        ),
    ],
)
async def test_prepare_prom_query_parameters(
    prometheus_last_scraped_timestamp: datetime,
    current_timestamp: datetime,
    expected: int,
):
    data: list[_PromQueryParameters] = _prepare_prom_query_parameters(
        "osparc.local", prometheus_last_scraped_timestamp, current_timestamp
    )
    assert len(data) == expected
    for current_item, next_item in zip(data, data[1:]):
        assert current_item.image_regex.startswith("registry.osparc.local")
        assert current_item.scrape_timestamp < next_item.scrape_timestamp

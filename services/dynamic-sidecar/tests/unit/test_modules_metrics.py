from collections.abc import Sequence
from datetime import datetime, timedelta
from typing import Final

import arrow
import pytest
from pydantic import NonNegativeFloat
from simcore_service_dynamic_sidecar.modules.metrics import (
    _MAX_DEFAULT_METRICS_SCRAPE_INTERVAL,
    _MAX_PROMETHEUS_SAMPLES,
    _get_user_services_scrape_interval,
)

_DT_REF: Final[datetime] = arrow.utcnow().datetime


@pytest.mark.parametrize(
    "input_query_times, expected",
    [
        pytest.param(
            [], _MAX_DEFAULT_METRICS_SCRAPE_INTERVAL, id="no_prometheus_queries"
        ),
        pytest.param(
            [_DT_REF],
            _MAX_DEFAULT_METRICS_SCRAPE_INTERVAL,
            id="too_few_prometheus_queries",
        ),
        ([_DT_REF, _DT_REF + timedelta(seconds=5)], 5),
        pytest.param(
            [_DT_REF, _DT_REF + timedelta(seconds=1000)],
            _MAX_DEFAULT_METRICS_SCRAPE_INTERVAL,
            id="prometheus_queries_too_far_apart",
        ),
        pytest.param(
            [
                _DT_REF + timedelta(seconds=i * 3)
                for i in range(_MAX_PROMETHEUS_SAMPLES)
            ],
            3,
            id="average_over_prometheus_queries",
        ),
    ],
)
def test_get_user_services_scrape_interval(
    input_query_times: Sequence[datetime], expected: NonNegativeFloat
):
    assert _get_user_services_scrape_interval(input_query_times) == expected

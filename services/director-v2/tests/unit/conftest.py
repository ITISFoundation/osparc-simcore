from asyncio import Future
from unittest.mock import patch

import pytest

from simcore_service_director_v2.modules.dynamic_sidecar.monitor.core import (
    DynamicSidecarsMonitor,
)


@pytest.fixture(scope="module", autouse=True)
def disable_dynamic_sidecar_monitor_in_unit_tests():
    future = Future()
    future.set_result(None)
    with patch.object(DynamicSidecarsMonitor, "start", return_value=future):
        yield

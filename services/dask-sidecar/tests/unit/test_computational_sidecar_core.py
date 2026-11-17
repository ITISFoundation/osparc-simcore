# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

from typing import Any

import pytest
from simcore_service_dask_sidecar.computational_sidecar.core import _OOM_EXIT_CODE, _is_oom_kill


@pytest.mark.parametrize(
    "container_state,expected",
    [
        pytest.param({"OOMKilled": True, "ExitCode": _OOM_EXIT_CODE}, True, id="oomkilled-flag"),
        pytest.param({"OOMKilled": False, "ExitCode": _OOM_EXIT_CODE}, True, id="sigkill-exit-without-flag"),
        pytest.param({"ExitCode": _OOM_EXIT_CODE}, True, id="sigkill-exit-missing-flag"),
        pytest.param({"OOMKilled": True, "ExitCode": 0}, True, id="flag-without-sigkill-exit"),
        pytest.param({"OOMKilled": False, "ExitCode": 1}, False, id="generic-service-failure"),
        pytest.param({"OOMKilled": False, "ExitCode": 0}, False, id="successful-exit"),
        pytest.param({}, False, id="empty-state"),
    ],
)
def test_is_oom_kill(container_state: dict[str, Any], expected: bool):
    assert _is_oom_kill(container_state) is expected

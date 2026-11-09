from types import SimpleNamespace
from typing import Any

import pytest
from pytest_simcore.docker_registry import _get_worker_registry_namespace


@pytest.mark.parametrize(
    "workerinput,expected_namespace",
    [
        pytest.param(None, "", id="no-xdist"),
        pytest.param({"workerid": "gw0"}, "gw0/", id="xdist-worker"),
    ],
)
def test_registry_namespace_is_per_worker_and_empty_outside_xdist(
    workerinput: dict[str, str] | None, expected_namespace: str
):
    request: Any = SimpleNamespace(config=SimpleNamespace(workerinput=workerinput))

    assert _get_worker_registry_namespace(request) == expected_namespace

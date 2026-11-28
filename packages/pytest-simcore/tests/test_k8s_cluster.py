from types import SimpleNamespace
from typing import Any

import pytest
from pytest_simcore.k8s_cluster import _reject_xdist_worker


def test_k8s_cluster_rejects_xdist_workers():
    request: Any = SimpleNamespace(config=SimpleNamespace(workerinput={"workerid": "gw0"}))

    with pytest.raises(pytest.UsageError, match="xdist"):
        _reject_xdist_worker(request)


def test_k8s_cluster_accepts_a_plain_session():
    request: Any = SimpleNamespace(config=SimpleNamespace(workerinput=None))

    _reject_xdist_worker(request)

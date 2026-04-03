import pytest
from pydantic import ValidationError
from simcore_service_dynamic_scheduler.services.p_scheduler._node_status._models import (
    ComponentPresence,
    ServicesPresence,
)

_A = ComponentPresence.ABSENT
_S = ComponentPresence.STARTING
_R = ComponentPresence.RUNNING
_F = ComponentPresence.FAILED


@pytest.mark.parametrize(
    "kwargs",
    [
        # all None → valid (no services detected)
        {},
        pytest.param({"legacy": None, "dy_sidecar": None, "dy_proxy": None}, id="all-none-explicit"),
        # legacy only → valid
        pytest.param({"legacy": _A}, id="legacy-absent"),
        pytest.param({"legacy": _S}, id="legacy-starting"),
        pytest.param({"legacy": _R}, id="legacy-running"),
        pytest.param({"legacy": _F}, id="legacy-failed"),
        # new-style: sidecar only → valid
        pytest.param({"dy_sidecar": _R}, id="sidecar-only"),
        pytest.param({"dy_sidecar": _A}, id="sidecar-absent-only"),
        # new-style: proxy only → valid
        pytest.param({"dy_proxy": _R}, id="proxy-only"),
        # new-style: both → valid
        pytest.param({"dy_sidecar": _R, "dy_proxy": _R}, id="both-new-style"),
        pytest.param({"dy_sidecar": _S, "dy_proxy": _A}, id="sidecar-starting-proxy-absent"),
        pytest.param({"dy_sidecar": _F, "dy_proxy": _F}, id="both-failed"),
    ],
)
def test_services_presence_valid(kwargs: dict) -> None:
    ServicesPresence(**kwargs)


@pytest.mark.parametrize(
    "kwargs",
    [
        # legacy + sidecar → invalid
        pytest.param({"legacy": _R, "dy_sidecar": _R}, id="legacy-and-sidecar"),
        # legacy + proxy → invalid
        pytest.param({"legacy": _R, "dy_proxy": _R}, id="legacy-and-proxy"),
        # legacy + both new-style → invalid
        pytest.param({"legacy": _R, "dy_sidecar": _R, "dy_proxy": _R}, id="legacy-and-both-new-style"),
        # all three set with different states
        pytest.param({"legacy": _A, "dy_sidecar": _S, "dy_proxy": _F}, id="all-three-mixed"),
    ],
)
def test_services_presence_invalid(kwargs: dict) -> None:
    with pytest.raises(ValidationError, match="Cannot have both legacy and new-style"):
        ServicesPresence(**kwargs)

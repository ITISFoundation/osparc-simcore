# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
"""Draft regression: a container removed mid-scan must not abort volume bookkeeping.

`get_unused_dynamic_sidecar_volumes` lists containers and then calls
`container.show()` per container. Under disk pressure swarm removes rejected
containers while the scan runs, and `show()` raises 404 `No such container`,
aborting the whole bookkeeping cycle (observed on osparc-master-03 at
2026-11-17 10:01 UTC, `master-simcore_master_agent`). Freeing unused volumes is
exactly what a full disk needs, so the cycle must survive the race.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from aiodocker.docker import DockerError
from servicelib.docker_constants import PREFIX_DYNAMIC_SIDECAR_VOLUMES
from simcore_service_agent.services.docker_utils import get_unused_dynamic_sidecar_volumes

_UNUSED_VOLUME = f"{PREFIX_DYNAMIC_SIDECAR_VOLUMES}unused_volume"
_USED_VOLUME = f"{PREFIX_DYNAMIC_SIDECAR_VOLUMES}used_volume"
_GONE_CONTAINER_ID = "container_removed_mid_scan"


def _container_showing(volume_name: str) -> AsyncMock:
    container = AsyncMock()
    container.show.return_value = {"Mounts": [{"Type": "volume", "Name": volume_name}]}
    return container


def _container_raising_gone() -> AsyncMock:
    container = AsyncMock()
    container.id = _GONE_CONTAINER_ID
    container.show.side_effect = DockerError(404, {"message": f"No such container: {_GONE_CONTAINER_ID}"})
    return container


@pytest.mark.xfail(
    strict=False,
    reason="regression draft (P5): the 404 from a container removed between "
    "containers.list() and container.show() currently aborts the whole scan",
)
async def test_scan_skips_container_removed_mid_scan() -> None:
    docker = MagicMock()
    docker.volumes.list = AsyncMock(return_value={"Volumes": [{"Name": _UNUSED_VOLUME}, {"Name": _USED_VOLUME}]})
    docker.containers.list = AsyncMock(return_value=[_container_showing(_USED_VOLUME), _container_raising_gone()])

    unused = await get_unused_dynamic_sidecar_volumes(docker)

    assert unused == {_UNUSED_VOLUME}

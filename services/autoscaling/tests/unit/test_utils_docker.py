# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import pytest
from aiodocker import DockerError
from fastapi import status
from simcore_service_autoscaling.utils_docker import (
    eval_cluster_resources,
    need_resources,
)


async def test_eval_cluster_resource_without_swarm():
    with pytest.raises(DockerError) as exc_info:
        await need_resources()

    assert exc_info.value.status == status.HTTP_503_SERVICE_UNAVAILABLE

    with pytest.raises(DockerError) as exc_info:
        await eval_cluster_resources()

    assert exc_info.value.status == status.HTTP_503_SERVICE_UNAVAILABLE

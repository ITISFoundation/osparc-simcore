# pylint: disable=no-value-for-parameter
# pylint: disable=redefined-outer-name


from typing import List

import pytest
from simcore_service_dask_sidecar.utils import cluster_id


@pytest.mark.parametrize(
    "docker_engine_labels, expected_id",
    [
        ({}, None),
        ({"invalidlabel"}, None),
        (["blahblah", "cluster_id=MyAwesomeClusterID"], "MyAwesomeClusterID"),
    ],
)
def test_cluster_id(docker_engine_labels: List[str], expected_id: str, mocker):
    mock_docker = mocker.patch(
        "simcore_service_dask_sidecar.utils.aiodocker.Docker", autospec=True
    )
    mock_docker.return_value.__aenter__.return_value.system.info.return_value = {
        "Labels": docker_engine_labels
    }
    the_cluster_id = cluster_id()
    assert the_cluster_id == expected_id

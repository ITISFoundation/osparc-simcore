# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import importlib.resources
from typing import Any

import pytest
import simcore_service_clusters_keeper.data
import yaml


@pytest.fixture
def clusters_keeper_docker_compose() -> dict[str, Any]:
    data = importlib.resources.read_text(
        simcore_service_clusters_keeper.data, "docker-compose.yml"
    )
    assert data
    return yaml.safe_load(data)


def _get_service_from_compose(
    compose: dict[str, Any], service_name: str
) -> dict[str, Any]:
    services = compose.get("services")
    assert services
    assert isinstance(services, dict)
    assert len(services) > 0
    assert service_name in services, f"{service_name} is missing from {services}"
    return services[service_name]


def test_redis_version_same_as_main_docker_compose(
    simcore_docker_compose: dict[str, Any],
    clusters_keeper_docker_compose: dict[str, Any],
):
    simcore_redis = _get_service_from_compose(simcore_docker_compose, "redis")
    clusters_keeper_redis = _get_service_from_compose(
        clusters_keeper_docker_compose, "redis"
    )

    assert simcore_redis["image"] == clusters_keeper_redis["image"]


def test_all_services_run_on_manager_but_dask_sidecar(
    clusters_keeper_docker_compose: dict[str, Any]
):
    for service_name, service_config in clusters_keeper_docker_compose[
        "services"
    ].items():
        assert "deploy" in service_config
        assert "placement" in service_config["deploy"]
        assert "constraints" in service_config["deploy"]["placement"]
        assert service_config["deploy"]["placement"]["constraints"] == [
            "node.role==worker"
            if service_name == "dask-sidecar"
            else "node.role==manager"
        ]

# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from typing import Any

import pytest


@pytest.fixture
def clusters_keeper_docker_compose() -> dict[str, Any]:
    return {}


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

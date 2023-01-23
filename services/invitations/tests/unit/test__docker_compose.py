# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from typing import Any

import pytest
from simcore_service_invitations._meta import API_VTAG


@pytest.fixture
def traefik_labels(services_docker_compose_specs: dict[str, str]) -> dict[str, Any]:
    labels: list[str] = services_docker_compose_specs["services"]["invitations"][
        "labels"
    ]
    return dict(tuple(l.split("=")) for l in labels if l.startswith("traefik."))


def test_traefik_is_enabled(
    traefik_labels: dict[str, str], openapi_specs: dict[str, Any]
):
    assert traefik_labels["traefik.enable"] == "true"


def test_traefik_healthcheck(
    traefik_labels: dict[str, str], openapi_specs: dict[str, Any]
):
    healthcheck_path = traefik_labels[
        "traefik.http.services.${SWARM_STACK_NAME}_invitations.loadbalancer.healthcheck.path"
    ]

    assert "health" in openapi_specs["paths"][healthcheck_path]["get"]["operationId"]


def test_traefik_api_in_routes(traefik_labels: dict[str, str]):
    assert (
        API_VTAG
        in traefik_labels["traefik.http.routers.${SWARM_STACK_NAME}_invitations.rule"]
    )

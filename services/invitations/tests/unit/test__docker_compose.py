# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from typing import Any

import pytest
from simcore_service_invitations._meta import API_VTAG


@pytest.fixture
def invitations_service_labels(
    services_docker_compose_specs: dict[str, str]
) -> dict[str, Any]:
    service = services_docker_compose_specs["services"]["invitations"]
    labels: list[str] = service["deploy"]["labels"]
    return dict(tuple(l.split("=")) for l in labels if l.startswith("traefik."))


def test_traefik_is_enabled(
    invitations_service_labels: dict[str, str], openapi_specs: dict[str, Any]
):
    assert invitations_service_labels["traefik.enable"] == "true"


def test_traefik_healthcheck(
    invitations_service_labels: dict[str, str], openapi_specs: dict[str, Any]
):
    healthcheck_path = invitations_service_labels[
        "traefik.http.services.${SWARM_STACK_NAME}_invitations.loadbalancer.healthcheck.path"
    ]

    assert "health" in openapi_specs["paths"][healthcheck_path]["get"]["operationId"]


def test_traefik_api_in_routes(invitations_service_labels: dict[str, str]):
    assert (
        API_VTAG
        in invitations_service_labels[
            "traefik.http.routers.${SWARM_STACK_NAME}_invitations.rule"
        ]
    )

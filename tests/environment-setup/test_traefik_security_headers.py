# pylint: disable=redefined-outer-name

from pathlib import Path
from typing import Final

import pytest
import yaml

_STACK: Final[str] = "${SWARM_STACK_NAME}"
_SECURITY_HEADERS_MIDDLEWARE: Final[str] = f"{_STACK}_security_headers"

_ROUTERS_WITH_SECURITY_HEADERS: Final[list[str]] = [
    f"{_STACK}_static_webserver",
    f"{_STACK}_webserver",
    f"{_STACK}_webserver_sticky",
]


@pytest.fixture(scope="module")
def traefik_labels_per_service(osparc_simcore_root_dir: Path) -> dict[str, dict[str, str]]:
    specs = yaml.safe_load((osparc_simcore_root_dir / "services" / "docker-compose.yml").read_text())

    labels_per_service: dict[str, dict[str, str]] = {}
    for name, service in specs["services"].items():
        labels: dict[str, str] = {}
        for label in service.get("deploy", {}).get("labels", []):
            key, _, value = label.partition("=")
            if key.startswith("traefik."):
                labels[key] = value
        labels_per_service[name] = labels
    return labels_per_service


def _router_middlewares(labels: dict[str, str], router: str) -> list[str]:
    value = labels.get(f"traefik.http.routers.{router}.middlewares", "")
    return [m.strip() for m in value.split(",")]


@pytest.mark.parametrize("router", _ROUTERS_WITH_SECURITY_HEADERS)
def test_security_headers_middleware_is_attached_to_router(
    traefik_labels_per_service: dict[str, dict[str, str]], router: str
):
    owners = [
        labels for labels in traefik_labels_per_service.values() if f"traefik.http.routers.{router}.rule" in labels
    ]
    assert len(owners) == 1

    assert f"{_SECURITY_HEADERS_MIDDLEWARE}@swarm" in _router_middlewares(owners[0], router)


@pytest.mark.parametrize("router", _ROUTERS_WITH_SECURITY_HEADERS)
def test_security_headers_middleware_is_defined_in_the_service_using_it(
    traefik_labels_per_service: dict[str, dict[str, str]], router: str
):
    # each service must be self-sufficient: the router is dropped by traefik
    # if a referenced middleware is missing (e.g. other service not deployed)
    (labels,) = [
        labels for labels in traefik_labels_per_service.values() if f"traefik.http.routers.{router}.rule" in labels
    ]
    prefix = f"traefik.http.middlewares.{_SECURITY_HEADERS_MIDDLEWARE}.headers"

    assert labels[f"{prefix}.referrerpolicy"] == "strict-origin-when-cross-origin"
    # an empty value makes traefik drop the header from the response
    assert labels[f"{prefix}.customresponseheaders.Server"] == ""

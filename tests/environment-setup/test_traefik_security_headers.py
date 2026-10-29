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
def traefik_labels(osparc_simcore_root_dir: Path) -> dict[str, str]:
    specs = yaml.safe_load((osparc_simcore_root_dir / "services" / "docker-compose.yml").read_text())

    labels: dict[str, str] = {}
    for service in specs["services"].values():
        for label in service.get("deploy", {}).get("labels", []):
            key, _, value = label.partition("=")
            if key.startswith("traefik."):
                labels[key] = value
    return labels


def test_security_headers_middleware_definition(traefik_labels: dict[str, str]):
    prefix = f"traefik.http.middlewares.{_SECURITY_HEADERS_MIDDLEWARE}.headers"

    assert traefik_labels[f"{prefix}.referrerpolicy"] == "strict-origin-when-cross-origin"
    # an empty value makes traefik drop the header from the response
    assert traefik_labels[f"{prefix}.customresponseheaders.Server"] == ""


@pytest.mark.parametrize("router", _ROUTERS_WITH_SECURITY_HEADERS)
def test_security_headers_middleware_is_attached_to_router(traefik_labels: dict[str, str], router: str):
    middlewares = [m.strip() for m in traefik_labels[f"traefik.http.routers.{router}.middlewares"].split(",")]

    assert f"{_SECURITY_HEADERS_MIDDLEWARE}@swarm" in middlewares


def test_referenced_security_headers_middleware_is_defined(traefik_labels: dict[str, str]):
    referenced = [
        router_label
        for router_label, value in traefik_labels.items()
        if router_label.endswith(".middlewares") and f"{_SECURITY_HEADERS_MIDDLEWARE}@" in value
    ]
    defined = any(key.startswith(f"traefik.http.middlewares.{_SECURITY_HEADERS_MIDDLEWARE}.") for key in traefik_labels)

    assert referenced
    assert defined

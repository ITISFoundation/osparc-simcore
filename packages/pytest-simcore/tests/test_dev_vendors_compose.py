import json
from typing import Final

from settings_library.utils_session import DEFAULT_SESSION_COOKIE_NAME

pytest_plugins = [
    "pytest_simcore.dev_vendors_compose",
    "pytest_simcore.docker_compose",
    "pytest_simcore.repository_paths",
]


_SERVICE_TO_MIDDLEWARE_MAPPING: Final[dict[str, str]] = {"manual": "pytest-simcore_manual-auth"}


def test_dev_vendors_docker_compose_auth_enabled(
    dev_vendors_docker_compose: dict[str, str],
):
    assert isinstance(dev_vendors_docker_compose["services"], dict)
    for service_name, service_spec in dev_vendors_docker_compose["services"].items():
        print(f"Checking vendor service '{service_name}'\n{json.dumps(service_spec, indent=2)}")
        labels = service_spec["deploy"]["labels"]

        # NOTE: when adding a new service it should also be added to the mapping
        auth_middleware_name = _SERVICE_TO_MIDDLEWARE_MAPPING[service_name]

        prefix = f"traefik.http.middlewares.{auth_middleware_name}.forwardauth"

        assert labels[f"{prefix}.trustForwardHeader"] == "true"
        assert "http://webserver:8080/v0/auth:check" in labels[f"{prefix}.address"]
        assert DEFAULT_SESSION_COOKIE_NAME in labels[f"{prefix}.authResponseHeaders"]
        assert auth_middleware_name in labels["traefik.http.routers.pytest-simcore_manual.middlewares"]

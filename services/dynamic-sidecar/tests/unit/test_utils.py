# pylint: disable=redefined-outer-name
import pytest
from _pytest.monkeypatch import MonkeyPatch
from settings_library.docker_registry import RegistrySettings
from simcore_service_dynamic_sidecar.core.utils import _is_registry_reachable

pytestmark = pytest.mark.asyncio

pytest_plugins = [
    "pytest_simcore.docker_registry",
    "pytest_simcore.docker_swarm",
]


@pytest.fixture
def registry_with_auth(
    monkeypatch: MonkeyPatch, docker_registry: str
) -> RegistrySettings:
    monkeypatch.setenv("REGISTRY_URL", docker_registry)
    monkeypatch.setenv("REGISTRY_AUTH", "false")
    monkeypatch.setenv("REGISTRY_AUTH", "true")
    monkeypatch.setenv("REGISTRY_USER", "testuser")
    monkeypatch.setenv("REGISTRY_PW", "testpassword")
    monkeypatch.setenv("REGISTRY_SSL", "false")
    return RegistrySettings()


async def test_is_registry_reachable(registry_with_auth: RegistrySettings) -> None:
    await _is_registry_reachable(registry_with_auth)

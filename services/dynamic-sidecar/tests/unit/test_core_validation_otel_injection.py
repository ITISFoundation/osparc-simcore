# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

from pathlib import Path

import pytest
import yaml
from fastapi import FastAPI
from models_library.projects_nodes_io import NodeID
from models_library.services_types import ServiceRunID
from pytest_mock import MockerFixture
from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict, setenvs_from_dict
from simcore_service_dynamic_sidecar.core.application import create_app
from simcore_service_dynamic_sidecar.core.settings import (
    ApplicationSettings,
    UserServiceTracingSettings,
)
from simcore_service_dynamic_sidecar.core.validation import (
    _OTEL_COLLECTOR_SERVICE_NAME,
    _build_otel_resource_attributes,
    _generate_otel_collector_config,
    _inject_otel_collector,
    get_and_validate_compose_spec,
)
from simcore_service_dynamic_sidecar.modules.mounted_fs import MountedVolumes


@pytest.fixture
def mock_get_volume_by_label(mocker: MockerFixture) -> None:
    mocker.patch(
        "simcore_service_dynamic_sidecar.modules.mounted_fs.get_volume_by_label",
        autospec=True,
        return_value={"Mountpoint": "/fake/mount"},
    )


@pytest.fixture
def mock_environment_with_tracing(
    mock_environment: EnvVarsDict,
    monkeypatch: pytest.MonkeyPatch,
) -> EnvVarsDict:
    return setenvs_from_dict(
        monkeypatch,
        {
            "TRACING_OPENTELEMETRY_COLLECTOR_ENDPOINT": "http://otel-collector.internal",
            "TRACING_OPENTELEMETRY_COLLECTOR_PORT": "4318",
            "TRACING_OPENTELEMETRY_SAMPLING_PROBABILITY": "1.0",
        },
    )


@pytest.fixture
def app_settings_with_tracing(
    mock_environment_with_tracing: EnvVarsDict,
) -> ApplicationSettings:
    return create_app().state.settings


@pytest.fixture
def user_tracing_settings(
    app_settings_with_tracing: ApplicationSettings,
) -> UserServiceTracingSettings:
    return app_settings_with_tracing.DYNAMIC_SIDECAR_USER_SERVICES_TRACING


@pytest.fixture
def fake_mounted_volumes(tmp_path: Path) -> MountedVolumes:
    dy_volumes = tmp_path / "dy-volumes"
    dy_volumes.mkdir(exist_ok=True)
    return MountedVolumes(
        service_run_id=ServiceRunID.get_resource_tracking_run_id_for_dynamic(),
        node_id=NodeID("a019b83f-7cce-46bf-90cf-d02f7f0f089a"),
        inputs_path=Path("/inputs"),
        outputs_path=Path("/outputs"),
        user_preferences_path=None,
        state_paths=[],
        state_exclude=set(),
        compose_namespace="",
        dy_volumes=dy_volumes,
    )


@pytest.fixture
def simple_compose_spec() -> str:
    return """
services:
  jupyter-lab:
    image: registry.osparc.org/simcore/services/dynamic/jupyter-lab:3.0.0
  data-processor:
    image: registry.osparc.org/simcore/services/dynamic/data-processor:1.0.0
version: '3.7'
    """


def test_generate_otel_collector_config_has_flush_interval(
    app_settings_with_tracing: ApplicationSettings,
    user_tracing_settings: UserServiceTracingSettings,
):
    config_yaml = _generate_otel_collector_config(user_tracing_settings, app_settings_with_tracing)
    config = yaml.safe_load(config_yaml)

    assert config["exporters"]["file"]["flush_interval"] == "10s"
    assert "max_elapsed" not in config["exporters"]["file"]["rotation"]


def test_generate_otel_collector_config_structure(
    app_settings_with_tracing: ApplicationSettings,
    user_tracing_settings: UserServiceTracingSettings,
):
    config_yaml = _generate_otel_collector_config(user_tracing_settings, app_settings_with_tracing)
    config = yaml.safe_load(config_yaml)

    assert "receivers" in config
    assert "otlp" in config["receivers"]
    assert "http" in config["receivers"]["otlp"]["protocols"]

    assert "processors" in config
    assert "batch" in config["processors"]
    assert "resource" in config["processors"]

    assert "exporters" in config
    assert "file" in config["exporters"]
    assert config["exporters"]["file"]["path"] == "/traces/spans.jsonl"
    assert "rotation" in config["exporters"]["file"]

    assert "service" in config
    assert "traces" in config["service"]["pipelines"]


def test_build_otel_resource_attributes(
    app_settings_with_tracing: ApplicationSettings,
):
    attrs = _build_otel_resource_attributes(app_settings_with_tracing)

    assert "simcore.user_id=" in attrs
    assert "simcore.project_id=" in attrs
    assert "simcore.node_id=" in attrs
    for part in attrs.split(","):
        key, value = part.split("=", 1)
        assert value, f"Empty value for key {key} should be excluded"


def test_inject_otel_collector_adds_service(
    app_settings_with_tracing: ApplicationSettings,
    user_tracing_settings: UserServiceTracingSettings,
):
    parsed_spec = {
        "version": "3.7",
        "services": {
            "jupyter-lab": {"image": "test:1.0", "environment": []},
            "data-processor": {"image": "test:2.0", "environment": []},
        },
    }

    container_name = _inject_otel_collector(
        parsed_spec,
        app_settings_with_tracing,
        user_tracing_settings,
        "/fake/mount:/traces",
        ["jupyter-lab", "data-processor"],
    )

    assert _OTEL_COLLECTOR_SERVICE_NAME in parsed_spec["services"]
    collector = parsed_spec["services"][_OTEL_COLLECTOR_SERVICE_NAME]
    assert collector["image"] == "otel/opentelemetry-collector:0.100.0"
    assert collector["stop_grace_period"] == "15s"
    assert "depends_on" not in collector
    assert "/fake/mount:/traces" in collector["volumes"]
    assert container_name

    # User services depend on collector (so Docker stops them first)
    for svc_key in ("jupyter-lab", "data-processor"):
        assert parsed_spec["services"][svc_key]["depends_on"] == [_OTEL_COLLECTOR_SERVICE_NAME]


async def test_validate_compose_spec_with_tracing_injects_otel(
    mock_get_volume_by_label: None,
    app_settings_with_tracing: ApplicationSettings,
    simple_compose_spec: str,
    fake_mounted_volumes: MountedVolumes,
):
    assert app_settings_with_tracing.is_tracing_enabled

    result = await get_and_validate_compose_spec(app_settings_with_tracing, simple_compose_spec, fake_mounted_volumes)

    parsed = yaml.safe_load(result.compose_spec)
    services = parsed["services"]

    # Collector should be present (with remapped container name, possibly truncated)
    collector_found = any("otel" in name for name in services)
    assert collector_found, f"Collector not found in services: {list(services.keys())}"

    # Each user service should have OTEL env vars
    for svc_name, svc_data in services.items():
        if "otel" in svc_name:
            continue
        env_list = svc_data.get("environment", {})
        if isinstance(env_list, list):
            env_str = "\n".join(env_list)
        else:
            env_str = "\n".join(f"{k}={v}" for k, v in env_list.items())

        assert "OTEL_EXPORTER_OTLP_ENDPOINT" in env_str, f"Missing OTEL endpoint in {svc_name}"
        assert "OTEL_SERVICE_NAME" in env_str, f"Missing OTEL service name in {svc_name}"
        assert "OTEL_RESOURCE_ATTRIBUTES" in env_str, f"Missing OTEL resource attrs in {svc_name}"


async def test_validate_compose_spec_without_tracing_no_otel(
    mock_get_volume_by_label: None,
    app: FastAPI,
    simple_compose_spec: str,
    fake_mounted_volumes: MountedVolumes,
):
    """Without tracing settings, no OTEL collector should be injected."""
    settings = app.state.settings
    assert not settings.is_tracing_enabled

    result = await get_and_validate_compose_spec(settings, simple_compose_spec, fake_mounted_volumes)

    parsed = yaml.safe_load(result.compose_spec)
    services = parsed["services"]

    collector_found = any("otel-collector" in name for name in services)
    assert not collector_found

    for svc_data in services.values():
        env_list = svc_data.get("environment", {})
        if isinstance(env_list, list):
            env_str = "\n".join(env_list)
        else:
            env_str = "\n".join(f"{k}={v}" for k, v in env_list.items())
        assert "OTEL_EXPORTER_OTLP_ENDPOINT" not in env_str

# pylint: disable=protected-access
# pylint: disable=redefined-outer-name

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest
import yaml
from aiodocker import DockerError
from fastapi import FastAPI, status
from settings_library.tracing import TracingSettings
from simcore_service_dynamic_sidecar.core.settings import ApplicationSettings
from simcore_service_dynamic_sidecar.modules.mounted_fs import MountedVolumes
from simcore_service_dynamic_sidecar.modules.user_services_tracing import (
    UserServicesTracingSettings,
    _otel_forwarder,
)

pytest_simcore_core_services_selection: list[str] = []
pytest_simcore_ops_services_selection: list[str] = []


def _docker_error(status_code: int) -> DockerError:
    return DockerError(status_code, {"message": f"error {status_code}"})


@pytest.fixture
def platform_tracing_settings_stub() -> TracingSettings:
    stub = Mock(spec=TracingSettings)
    stub.TRACING_OPENTELEMETRY_COLLECTOR_IMAGE_VERSION = "0.144.0"
    stub.TRACING_OPENTELEMETRY_COLLECTOR_ENDPOINT = "http://platform-collector.testing"
    stub.TRACING_OPENTELEMETRY_COLLECTOR_PORT = 4318
    stub.TRACING_OPENTELEMETRY_SAMPLING_PROBABILITY = 1.0
    return stub


@pytest.fixture
def user_services_tracing_settings() -> UserServicesTracingSettings:
    return UserServicesTracingSettings()


@pytest.fixture
def settings_stub(
    platform_tracing_settings_stub: TracingSettings,
    user_services_tracing_settings: UserServicesTracingSettings,
) -> ApplicationSettings:
    stub = Mock(spec=ApplicationSettings)
    stub.DYNAMIC_SIDECAR_COMPOSE_NAMESPACE = "dy-sidecar_test_namespace"
    stub.DY_SIDECAR_RUN_ID = "run-id-123"
    stub.DY_SIDECAR_NODE_ID = "node-id-456"
    stub.DYNAMIC_SIDECAR_TRACING = platform_tracing_settings_stub
    stub.DYNAMIC_SIDECAR_USER_SERVICES_TRACING_CONFIG = user_services_tracing_settings
    return stub


@pytest.fixture
def mounted_volumes_stub(tmp_path: Path) -> MountedVolumes:
    traces_path = tmp_path / "traces"
    traces_path.mkdir()
    stub = Mock(spec=MountedVolumes)
    stub.disk_traces_path = traces_path
    stub.get_traces_docker_volume = AsyncMock(return_value=f"{traces_path}:/traces")
    return stub


@pytest.fixture
def app_stub(settings_stub: ApplicationSettings, mounted_volumes_stub: MountedVolumes) -> FastAPI:
    app = Mock(spec=FastAPI)
    app.state = Mock()
    app.state.settings = settings_stub
    app.state.mounted_volumes = mounted_volumes_stub
    return app


@pytest.fixture
def docker_client_stub(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    """Patches ``_docker_client`` to yield a controllable mock aiodocker client."""
    client = AsyncMock()

    @asynccontextmanager
    async def _cm() -> AsyncIterator[AsyncMock]:
        yield client

    monkeypatch.setattr(_otel_forwarder, "_docker_client", _cm)
    return client


#
# config generation
#


def test_generate_forwarder_config_reads_files_and_ships_to_platform(
    platform_tracing_settings_stub: Mock,
):
    config = yaml.safe_load(_otel_forwarder._generate_forwarder_config(platform_tracing_settings_stub))  # noqa: SLF001

    receiver = config["receivers"]["otlpjsonfile"]
    assert receiver["include"] == ["/traces/spans*.jsonl"]
    assert receiver["start_at"] == "beginning"
    # the live file is tailed by persisted offset and NEVER deleted (the injected collector
    # keeps it open and would keep appending to a deleted inode -> dropped spans)
    assert "delete_after_read" not in receiver
    assert receiver["storage"] == "file_storage/forwarder"

    exporter = config["exporters"]["otlp_http"]
    assert exporter["traces_endpoint"] == "http://platform-collector.testing:4318/v1/traces"
    assert exporter["retry_on_failure"]["enabled"] is True
    assert exporter["sending_queue"]["storage"] == "file_storage/forwarder"

    assert "file_storage/forwarder" in config["extensions"]
    # the state dir lives on the shared volume and must be auto-created on first boot
    assert config["extensions"]["file_storage/forwarder"]["create_directory"] is True
    assert config["service"]["pipelines"]["traces"] == {
        "receivers": ["otlpjsonfile"],
        "exporters": ["otlp_http"],
    }
    assert config["service"]["extensions"] == ["file_storage/forwarder"]


def test_platform_otlp_traces_endpoint(platform_tracing_settings_stub: Mock):
    assert (
        _otel_forwarder._platform_otlp_traces_endpoint(platform_tracing_settings_stub)  # noqa: SLF001
        == "http://platform-collector.testing:4318/v1/traces"
    )


def test_build_forwarder_container_config(
    settings_stub: ApplicationSettings,
    user_services_tracing_settings: UserServicesTracingSettings,
    platform_tracing_settings_stub: Mock,
):
    config = _otel_forwarder._build_forwarder_container_config(  # noqa: SLF001
        settings=settings_stub,
        user_services_tracing_settings=user_services_tracing_settings,
        platform_tracing_settings=platform_tracing_settings_stub,
        traces_volume_bind="/host/traces:/traces",
    )

    assert config["Image"] == (f"{user_services_tracing_settings.USER_SERVICES_TRACING_COLLECTOR_IMAGE_NAME}:0.144.0")
    host_config = config["HostConfig"]
    assert isinstance(host_config, dict)
    assert host_config["Binds"] == ["/host/traces:/traces"]
    assert isinstance(host_config["NetworkMode"], str)
    assert host_config["NetworkMode"].startswith("container:")  # shares sidecar netns
    assert host_config["RestartPolicy"] == {"Name": "unless-stopped"}
    # resource caps (Docker Engine API equivalents of compose mem_limit/cpus/cpu_shares)
    assert host_config["Memory"] == user_services_tracing_settings.USER_SERVICES_TRACING_COLLECTOR_MEMORY_LIMIT
    assert host_config["NanoCpus"] == int(
        user_services_tracing_settings.USER_SERVICES_TRACING_COLLECTOR_CPU_LIMIT * _otel_forwarder._NANO_CPUS_PER_CORE  # noqa: SLF001
    )
    assert host_config["CpuShares"] == user_services_tracing_settings.USER_SERVICES_TRACING_COLLECTOR_CPU_SHARES
    assert config["Env"] == [
        f"OTEL_COLLECTOR_CONFIG={_otel_forwarder._generate_forwarder_config(platform_tracing_settings_stub)}"  # noqa: SLF001
    ]
    # no file deletion -> the filelog.allowFileDeletion feature gate must NOT be set
    assert not any("filelog.allowFileDeletion" in arg for arg in config["Cmd"])
    assert config["Labels"]["io.simcore.dynamic-sidecar.trace-forwarder"] == "true"


#
# idempotent create
#


async def test_create_collector_runs_container(app_stub: FastAPI, docker_client_stub: AsyncMock):
    await _otel_forwarder.create_user_services_trace_collector(app_stub)

    docker_client_stub.containers.run.assert_awaited_once()
    _, kwargs = docker_client_stub.containers.run.call_args
    assert kwargs["name"] == _otel_forwarder._forwarder_container_name(app_stub.state.settings)  # noqa: SLF001


async def test_create_collector_is_idempotent_on_conflict(app_stub: FastAPI, docker_client_stub: AsyncMock):
    docker_client_stub.containers.run.side_effect = _docker_error(status.HTTP_409_CONFLICT)

    # must NOT raise: the forwarder already exists
    await _otel_forwarder.create_user_services_trace_collector(app_stub)


async def test_create_collector_reraises_unexpected_errors(app_stub: FastAPI, docker_client_stub: AsyncMock):
    docker_client_stub.containers.run.side_effect = _docker_error(status.HTTP_500_INTERNAL_SERVER_ERROR)

    with pytest.raises(DockerError):
        await _otel_forwarder.create_user_services_trace_collector(app_stub)


#
# idempotent remove
#


async def test_remove_collector_is_idempotent_when_absent(app_stub: FastAPI, docker_client_stub: AsyncMock):
    docker_client_stub.containers.get.side_effect = _docker_error(status.HTTP_404_NOT_FOUND)

    # must NOT raise when the container is already gone
    await _otel_forwarder.remove_user_services_trace_collector(app_stub)


async def test_remove_collector_stops_and_deletes(app_stub: FastAPI, docker_client_stub: AsyncMock):
    container = AsyncMock()
    docker_client_stub.containers.get.return_value = container

    await _otel_forwarder.remove_user_services_trace_collector(app_stub)

    container.stop.assert_awaited_once()
    container.delete.assert_awaited_once_with(force=True)


#
# enablement gate
#


@pytest.mark.parametrize("tracing_enabled", [True, False])
@pytest.mark.parametrize("opt_in", [True, False])
def test_is_user_services_tracing_enabled(
    monkeypatch: pytest.MonkeyPatch,
    app_stub: FastAPI,
    tracing_enabled: bool,
    opt_in: bool,
):
    app_stub.state.settings.DY_SIDECAR_USER_SERVICES_TRACING_OPT_IN = opt_in
    monkeypatch.setattr(_otel_forwarder, "get_tracing_config", lambda _app: Mock(tracing_enabled=tracing_enabled))

    assert _otel_forwarder.is_user_services_tracing_enabled(app_stub) is (tracing_enabled and opt_in)

# pylint: disable=unused-argument,redefined-outer-name,no-member
import pytest
import asyncio

from simcore_service_sidecar.celery_configurator import (
    get_rabbitmq_config_and_celery_app,
)
from simcore_service_sidecar.utils import is_gpu_node
from simcore_service_sidecar import config

from celery import Celery
from simcore_sdk.config.rabbit import Config as RabbitConfig


def _toggle_gpu_mock(mocker, has_gpu: bool) -> None:
    # mock ouput of cat /proc/self/cgroup
    CAT_DATA = b"""
    12:hugetlb:/docker/2c52ab5a825dea0b074741fb1521c972866af7997a761eb312405b50ad289263
    11:freezer:/docker/2c52ab5a825dea0b074741fb1521c972866af7997a761eb312405b50ad289263
    10:blkio:/docker/2c52ab5a825dea0b074741fb1521c972866af7997a761eb312405b50ad289263
    9:devices:/docker/2c52ab5a825dea0b074741fb1521c972866af7997a761eb312405b50ad289263
    8:net_cls,net_prio:/docker/2c52ab5a825dea0b074741fb1521c972866af7997a761eb312405b50ad289263
    7:cpuset:/docker/2c52ab5a825dea0b074741fb1521c972866af7997a761eb312405b50ad289263
    6:perf_event:/docker/2c52ab5a825dea0b074741fb1521c972866af7997a761eb312405b50ad289263
    5:memory:/docker/2c52ab5a825dea0b074741fb1521c972866af7997a761eb312405b50ad289263
    4:rdma:/
    3:cpu,cpuacct:/docker/2c52ab5a825dea0b074741fb1521c972866af7997a761eb312405b50ad289263
    2:pids:/docker/2c52ab5a825dea0b074741fb1521c972866af7997a761eb312405b50ad289263
    1:name=systemd:/docker/2c52ab5a825dea0b074741fb1521c972866af7997a761eb312405b50ad289263
    0::/system.slice/containerd.service
    """

    future = asyncio.Future()
    future.set_result((CAT_DATA, None))
    comunicate = mocker.patch("asyncio.subprocess.Process.communicate")
    comunicate.return_value = future

    class MockContainer:
        async def show(self):
            data = {"Config": {"Labels": {"com.docker.swarm.node.id": "node_id"}}}
            return data

    future = asyncio.Future()
    future.set_result(MockContainer())
    containers_get = mocker.patch("aiodocker.containers.DockerContainers.get")
    containers_get.return_value = future

    def gpu_support_key():
        """if GPU support is enabled this Kind key must be present"""
        return "Kind" if has_gpu else "_"

    payload = {
        "Description": {
            "Resources": {
                "GenericResources": [
                    {"DiscreteResourceSpec": {gpu_support_key(): "VRAM"}}
                ]
            }
        }
    }

    future = asyncio.Future()
    future.set_result(payload)
    containers_get = mocker.patch("aiodocker.nodes.DockerSwarmNodes.inspect")
    containers_get.return_value = future


@pytest.fixture()
def mock_node_no_gpu(mocker) -> None:
    _toggle_gpu_mock(mocker, False)


@pytest.fixture()
def mock_node_with_gpu(mocker) -> None:
    _toggle_gpu_mock(mocker, True)


@pytest.fixture(params=[True, False])
def mock_node_has_gpu(request, mocker) -> None:
    _toggle_gpu_mock(mocker, request.param)


@pytest.fixture
def force_cpu_mode(monkeypatch):
    monkeypatch.setattr(config, "FORCE_START_CPU_MODE", "1", raising=True)


@pytest.fixture
def force_gpu_mode(monkeypatch):
    monkeypatch.setattr(config, "FORCE_START_GPU_MODE", "1", raising=True)


@pytest.mark.parametrize("gpu_support", [(pytest.lazy_fixture("mock_node_has_gpu")),])
def test_force_start_cpu_mode(mocker, force_cpu_mode, gpu_support) -> None:
    mocked_configure_cpu_mode = mocker.patch(
        "simcore_service_sidecar.celery_configurator.configure_cpu_mode"
    )

    mocked_configure_cpu_mode.return_value = (None, None)

    get_rabbitmq_config_and_celery_app()

    mocked_configure_cpu_mode.assert_called()


@pytest.mark.parametrize("gpu_support", [(pytest.lazy_fixture("mock_node_has_gpu")),])
def test_force_start_gpu_mode(mocker, force_gpu_mode, gpu_support) -> None:
    mocked_configure_gpu_mode = mocker.patch(
        "simcore_service_sidecar.celery_configurator.configure_gpu_mode"
    )
    mocked_configure_gpu_mode.return_value = (None, None)

    get_rabbitmq_config_and_celery_app()

    mocked_configure_gpu_mode.assert_called()


def test_auto_detects_gpu(mocker, mock_node_with_gpu) -> None:
    mocked_configure_gpu_mode = mocker.patch(
        "simcore_service_sidecar.celery_configurator.configure_gpu_mode"
    )
    mocked_configure_gpu_mode.return_value = (None, None)

    get_rabbitmq_config_and_celery_app()

    mocked_configure_gpu_mode.assert_called()


@pytest.mark.parametrize(
    "gpu_support,expected_value",
    [
        (pytest.lazy_fixture("mock_node_no_gpu"), False),
        (pytest.lazy_fixture("mock_node_with_gpu"), True),
    ],
)
def test_proper_has_gpu_mocking(expected_value, gpu_support) -> None:
    assert is_gpu_node() is expected_value


@pytest.mark.parametrize("gpu_support", [(pytest.lazy_fixture("mock_node_has_gpu")),])
def test_force_start_cpu_ext_dep_mocking(force_cpu_mode, gpu_support) -> None:
    rabbit_cfg, celery_app = get_rabbitmq_config_and_celery_app()
    assert isinstance(rabbit_cfg, RabbitConfig)
    assert isinstance(celery_app, Celery)


@pytest.mark.parametrize("gpu_support", [(pytest.lazy_fixture("mock_node_has_gpu")),])
def test_force_start_gpu_ext_dep_mocking(force_gpu_mode, gpu_support) -> None:
    rabbit_cfg, celery_app = get_rabbitmq_config_and_celery_app()
    assert isinstance(rabbit_cfg, RabbitConfig)
    assert isinstance(celery_app, Celery)

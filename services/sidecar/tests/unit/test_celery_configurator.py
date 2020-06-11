# pylint: disable=unused-argument,redefined-outer-name,no-member
import pytest
import asyncio

from simcore_service_sidecar.celery_configurator import (
    get_rabbitmq_config_and_celery_app,
)
from simcore_service_sidecar.utils import is_gpu_node

from celery import Celery
from simcore_sdk.config.rabbit import Config as RabbitConfig


def _toggle_gpy_mock(mocker, has_gpu: bool) -> None:
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
def mock_no_gpu(mocker) -> None:
    _toggle_gpy_mock(mocker, False)


@pytest.fixture()
def mock_with_gpu(mocker) -> None:
    _toggle_gpy_mock(mocker, True)


@pytest.fixture(params=[True, False])
def mock_gpu_both_modes(request, mocker):
    return _toggle_gpy_mock(mocker, request.param)


def test_force_start_cpu_mode(mocker, mock_no_gpu, monkeypatch):
    monkeypatch.setenv("START_AS_MODE_CPU", "1")

    mocked_configure_cpu_mode = mocker.patch(
        "simcore_service_sidecar.celery_configurator.configure_cpu_mode"
    )

    mocked_configure_cpu_mode.return_value = (None, None)

    get_rabbitmq_config_and_celery_app()

    mocked_configure_cpu_mode.assert_called()


def test_force_start_gpu_mode(mocker, mock_no_gpu, monkeypatch):
    monkeypatch.setenv("START_AS_MODE_GPU", "1")

    mocked_configure_gpu_mode = mocker.patch(
        "simcore_service_sidecar.celery_configurator.configure_gpu_mode"
    )
    mocked_configure_gpu_mode.return_value = (None, None)

    get_rabbitmq_config_and_celery_app()

    mocked_configure_gpu_mode.assert_called()


def test_auto_detects_gpu(mocker, mock_with_gpu, monkeypatch):
    mocked_configure_gpu_mode = mocker.patch(
        "simcore_service_sidecar.celery_configurator.configure_gpu_mode"
    )
    mocked_configure_gpu_mode.return_value = (None, None)

    get_rabbitmq_config_and_celery_app()

    mocked_configure_gpu_mode.assert_called()


@pytest.mark.parametrize(
    "gpu_support,expected_value",
    [
        (pytest.lazy_fixture("mock_no_gpu"), False),
        (pytest.lazy_fixture("mock_with_gpu"), True),
    ],
)
def test_proper_has_gpu_mocking(expected_value, gpu_support):
    assert is_gpu_node() is expected_value


@pytest.mark.parametrize("gpu_support", [(pytest.lazy_fixture("mock_gpu_both_modes")),])
def test_force_start_cpu_mode_no_mocks(monkeypatch, gpu_support):
    monkeypatch.setenv("START_AS_MODE_CPU", "1")

    rabbit_cfg, celery_app = get_rabbitmq_config_and_celery_app()
    assert isinstance(rabbit_cfg, RabbitConfig)
    assert isinstance(celery_app, Celery)


@pytest.mark.parametrize("gpu_support", [(pytest.lazy_fixture("mock_gpu_both_modes")),])
def test_force_start_gpu_mode_no_mocks(gpu_support, monkeypatch):
    monkeypatch.setenv("START_AS_MODE_GPU", "1")

    rabbit_cfg, celery_app = get_rabbitmq_config_and_celery_app()
    assert isinstance(rabbit_cfg, RabbitConfig)
    assert isinstance(celery_app, Celery)

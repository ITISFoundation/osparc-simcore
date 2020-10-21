# pylint: disable=unused-argument,redefined-outer-name,no-member
import asyncio

import aiodocker
import pytest
from celery import Celery
from simcore_service_sidecar import config
from simcore_service_sidecar.boot_mode import BootMode
from simcore_service_sidecar.celery_configurator import create_celery_app
from simcore_service_sidecar.utils import is_gpu_node


def _toggle_gpu_mock(mocker, has_gpu: bool) -> None:
    containers_get = mocker.patch(
        "aiodocker.containers.DockerContainers.run", return_value=asyncio.Future()
    )
    containers_get.return_value.set_result("")
    if not has_gpu:
        containers_get.side_effect = aiodocker.exceptions.DockerError(
            "MOCK Error", {"message": "this is a mocked exception"}
        )


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


@pytest.mark.parametrize(
    "gpu_support",
    [
        (pytest.lazy_fixture("mock_node_has_gpu")),
    ],
)
def test_force_start_cpu_mode(mocker, force_cpu_mode, gpu_support) -> None:
    mocked_configure_cpu_mode = mocker.patch(
        "simcore_service_sidecar.celery_configurator.configure_node"
    )

    mocked_configure_cpu_mode.return_value = None

    create_celery_app()

    mocked_configure_cpu_mode.assert_called_with(BootMode.CPU)


@pytest.mark.parametrize(
    "gpu_support",
    [
        (pytest.lazy_fixture("mock_node_has_gpu")),
    ],
)
def test_force_start_gpu_mode(mocker, force_gpu_mode, gpu_support) -> None:
    mocked_configure_gpu_mode = mocker.patch(
        "simcore_service_sidecar.celery_configurator.configure_node"
    )
    mocked_configure_gpu_mode.return_value = None

    create_celery_app()

    mocked_configure_gpu_mode.assert_called_with(BootMode.GPU)


def test_auto_detects_gpu(mocker, mock_node_with_gpu) -> None:
    mocked_configure_gpu_mode = mocker.patch(
        "simcore_service_sidecar.celery_configurator.configure_node"
    )
    mocked_configure_gpu_mode.return_value = None

    create_celery_app()

    mocked_configure_gpu_mode.assert_called_with(BootMode.GPU)


@pytest.mark.parametrize(
    "gpu_support,expected_value",
    [
        (pytest.lazy_fixture("mock_node_no_gpu"), False),
        (pytest.lazy_fixture("mock_node_with_gpu"), True),
    ],
)
def test_proper_has_gpu_mocking(expected_value, gpu_support) -> None:
    assert is_gpu_node() is expected_value


@pytest.mark.parametrize(
    "gpu_support",
    [
        (pytest.lazy_fixture("mock_node_has_gpu")),
    ],
)
def test_force_start_cpu_ext_dep_mocking(force_cpu_mode, gpu_support) -> None:
    celery_app = create_celery_app()
    assert isinstance(celery_app, Celery)


@pytest.mark.parametrize(
    "gpu_support",
    [
        (pytest.lazy_fixture("mock_node_has_gpu")),
    ],
)
def test_force_start_gpu_ext_dep_mocking(force_gpu_mode, gpu_support) -> None:
    celery_app = create_celery_app()
    assert isinstance(celery_app, Celery)

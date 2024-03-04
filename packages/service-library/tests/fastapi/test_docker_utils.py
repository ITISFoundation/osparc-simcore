# pylint: disable=protected-access
from collections.abc import Awaitable, Callable
from typing import Any
from unittest.mock import call

import pytest
from models_library.docker import DockerGenericTag
from pydantic import parse_obj_as
from pytest_mock import MockerFixture
from servicelib import progress_bar
from servicelib.docker_utils import pull_image
from servicelib.fastapi.docker_utils import retrieve_image_layer_information
from settings_library.docker_registry import RegistrySettings


@pytest.mark.parametrize(
    "service_repo, service_tag",
    [
        ("itisfoundation/sleeper", "1.0.0"),
        ("itisfoundation/sleeper", "2.2.0"),
        (
            "itisfoundation/sleeper",
            "sha256:a6d9886311721d8d341068361ecf9998a3c7ecb0efb23ebac553602c2eca1f8f",
        ),
    ],
)
async def test_retrieve_image_layer_information(
    remove_images_from_host: Callable[[list[str]], Awaitable[None]],
    registry_settings: RegistrySettings,
    osparc_service: dict[str, Any],
    service_repo: str,
    service_tag: str,
):
    # clean first
    image_name = f"{service_repo}:{service_tag}"
    if "sha256" in service_tag:
        image_name = f"{service_repo}@{service_tag}"
    await remove_images_from_host([image_name])
    docker_image = parse_obj_as(
        DockerGenericTag,
        f"{registry_settings.REGISTRY_URL}/{osparc_service['image']['name']}:{osparc_service['image']['tag']}",
    )
    layer_information = await retrieve_image_layer_information(
        docker_image, registry_settings
    )

    assert layer_information


@pytest.mark.parametrize(
    "image",
    [
        "itisfoundation/dask-sidecar:master-github-latest",
        "library/nginx:latest",
        "nginx:1.25.4",
        "nginx:latest",
        "ubuntu@sha256:81bba8d1dde7fc1883b6e95cd46d6c9f4874374f2b360c8db82620b33f6b5ca1",
        "busybox:latest",
    ],
)
async def test_retrieve_image_layer_information_from_external_registry(
    remove_images_from_host: Callable[[list[str]], Awaitable[None]],
    image: DockerGenericTag,
    registry_settings: RegistrySettings,
):
    # clean first
    await remove_images_from_host([image])
    layer_information = await retrieve_image_layer_information(image, registry_settings)
    assert layer_information


@pytest.mark.parametrize(
    "image",
    ["itisfoundation/sleeper:1.0.0", "nginx:latest", "busybox:latest"],
)
async def test_pull_image(
    remove_images_from_host: Callable[[list[str]], Awaitable[None]],
    image: DockerGenericTag,
    registry_settings: RegistrySettings,
    mocker: MockerFixture,
    caplog: pytest.LogCaptureFixture,
):
    await remove_images_from_host([image])
    layer_information = await retrieve_image_layer_information(image, registry_settings)

    async def _log_cb(*args, **kwargs) -> None:
        print(f"received log: {args}, {kwargs}")

    fake_progress_report_cb = mocker.AsyncMock()
    async with progress_bar.ProgressBarData(
        num_steps=1, progress_report_cb=fake_progress_report_cb
    ) as main_progress_bar:
        fake_log_cb = mocker.AsyncMock(side_effect=_log_cb)
        await pull_image(
            image, registry_settings, main_progress_bar, fake_log_cb, layer_information
        )
        fake_log_cb.assert_called()
        assert main_progress_bar._current_steps == 1  # noqa: SLF001
    assert fake_progress_report_cb.call_args_list[0] == call(0.0)
    fake_progress_report_cb.assert_called_with(1.0)
    fake_progress_report_cb.reset_mock()

    # check there were no warnings
    # NOTE: this would pop up in case docker changes its pulling statuses
    for record in caplog.records:
        assert record.levelname != "WARNING", record.message

    # pull a second time should, the image is already there
    async with progress_bar.ProgressBarData(
        num_steps=1, progress_report_cb=fake_progress_report_cb
    ) as main_progress_bar:
        fake_log_cb = mocker.AsyncMock(side_effect=_log_cb)
        await pull_image(
            image, registry_settings, main_progress_bar, fake_log_cb, layer_information
        )
        fake_log_cb.assert_called()
        assert main_progress_bar._current_steps == 1  # noqa: SLF001
    assert fake_progress_report_cb.call_args_list[0] == call(0.0)
    fake_progress_report_cb.assert_called_with(1.0)
    # check there were no warnings
    for record in caplog.records:
        assert record.levelname != "WARNING", record.message

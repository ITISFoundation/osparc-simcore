# pylint: disable=protected-access
from datetime import datetime, timezone
from typing import Any

import pytest
from models_library.docker import DockerGenericTag
from pydantic import ByteSize, parse_obj_as
from pytest_mock import MockerFixture
from servicelib import progress_bar
from servicelib.docker_utils import (
    pull_image,
    retrieve_image_layer_information,
    to_datetime,
)
from settings_library.docker_registry import RegistrySettings

NOW = datetime.now(tz=timezone.utc)


@pytest.mark.parametrize(
    "docker_time, expected_datetime",
    [
        (
            "2023-03-21T00:00:00Z",
            datetime(2023, 3, 21, 0, 0, tzinfo=timezone.utc),
        ),
        (
            "2023-12-31T23:59:59Z",
            datetime(2023, 12, 31, 23, 59, 59, tzinfo=timezone.utc),
        ),
        (
            "2020-10-09T12:28:14.771034099Z",
            datetime(2020, 10, 9, 12, 28, 14, 771034, tzinfo=timezone.utc),
        ),
        (
            "2020-10-09T12:28:14.123456099Z",
            datetime(2020, 10, 9, 12, 28, 14, 123456, tzinfo=timezone.utc),
        ),
        (
            "2020-10-09T12:28:14.12345Z",
            datetime(2020, 10, 9, 12, 28, 14, 123450, tzinfo=timezone.utc),
        ),
        (
            "2023-03-15 13:01:21.774501",
            datetime(2023, 3, 15, 13, 1, 21, 774501, tzinfo=timezone.utc),
        ),
        (f"{NOW}", NOW),
        (NOW.strftime("%Y-%m-%dT%H:%M:%S.%f"), NOW),
    ],
)
def test_to_datetime(docker_time: str, expected_datetime: datetime):
    received_datetime = to_datetime(docker_time)
    assert received_datetime == expected_datetime


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
    registry_settings: RegistrySettings, osparc_service: dict[str, Any]
):
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
    ],
)
async def test_retrieve_image_layer_information_from_external_registry(
    image: DockerGenericTag, registry_settings: RegistrySettings
):
    layer_information = await retrieve_image_layer_information(image, registry_settings)
    assert layer_information


@pytest.mark.parametrize(
    "image",
    [
        "itisfoundation/sleeper:1.0.0",
    ],
)
async def test_pull_image(
    image: DockerGenericTag, registry_settings: RegistrySettings, mocker: MockerFixture
):
    layer_information = await retrieve_image_layer_information(image, registry_settings)
    image_total_size: ByteSize = ByteSize(0)
    for layer in layer_information.layers:
        image_total_size = ByteSize(image_total_size + layer.size)

    async def _log_cb(*args, **kwargs) -> None:
        print(f"received log: {args}, {kwargs}")

    async with progress_bar.ProgressBarData(num_steps=1) as main_progress_bar:
        fake_log_cb = mocker.AsyncMock(side_effect=_log_cb)
        await pull_image(
            image, registry_settings, main_progress_bar, fake_log_cb, layer_information
        )
        fake_log_cb.assert_called()
        assert main_progress_bar._current_steps == 1  # noqa: SLF001

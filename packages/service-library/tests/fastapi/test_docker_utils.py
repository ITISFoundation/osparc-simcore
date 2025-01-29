# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable
import asyncio
from collections.abc import Awaitable, Callable
from typing import Any
from unittest import mock

import pytest
from faker import Faker
from models_library.docker import DockerGenericTag
from models_library.progress_bar import ProgressReport
from pydantic import ByteSize, TypeAdapter
from pytest_mock import MockerFixture
from servicelib import progress_bar
from servicelib.docker_utils import pull_image
from servicelib.fastapi.docker_utils import (
    pull_images,
    retrieve_image_layer_information,
)
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
    docker_image = TypeAdapter(DockerGenericTag).validate_python(
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


@pytest.fixture
async def mocked_log_cb(mocker: MockerFixture) -> mock.AsyncMock:
    async def _log_cb(*args, **kwargs) -> None:
        print(f"received log: {args}, {kwargs}")

    return mocker.AsyncMock(side_effect=_log_cb)


@pytest.fixture
async def mocked_progress_cb(mocker: MockerFixture) -> mock.AsyncMock:
    async def _progress_cb(*args, **kwargs) -> None:
        print(f"received progress: {args}, {kwargs}")
        assert isinstance(args[0], ProgressReport)

    return mocker.AsyncMock(side_effect=_progress_cb)


def _assert_progress_report_values(
    mocked_progress_cb: mock.AsyncMock, *, total: float
) -> None:
    # NOTE: we exclude the message part here as this is already tested in servicelib
    # check first progress
    assert mocked_progress_cb.call_args_list[0].args[0].dict(
        exclude={"message"}
    ) == ProgressReport(actual_value=0, total=total, unit="Byte").model_dump(
        exclude={"message"}
    )
    # check last progress
    assert mocked_progress_cb.call_args_list[-1].args[0].dict(
        exclude={"message"}
    ) == ProgressReport(actual_value=total, total=total, unit="Byte").model_dump(
        exclude={"message"}
    )


@pytest.mark.parametrize(
    "image",
    ["itisfoundation/sleeper:1.0.0", "nginx:latest", "busybox:latest"],
)
async def test_pull_image(
    remove_images_from_host: Callable[[list[str]], Awaitable[None]],
    image: DockerGenericTag,
    registry_settings: RegistrySettings,
    mocked_log_cb: mock.AsyncMock,
    mocked_progress_cb: mock.AsyncMock,
    caplog: pytest.LogCaptureFixture,
    faker: Faker,
):
    await remove_images_from_host([image])
    layer_information = await retrieve_image_layer_information(image, registry_settings)
    assert layer_information

    async with progress_bar.ProgressBarData(
        num_steps=layer_information.layers_total_size,
        progress_report_cb=mocked_progress_cb,
        progress_unit="Byte",
        description=faker.pystr(),
    ) as main_progress_bar:

        await pull_image(
            image,
            registry_settings,
            main_progress_bar,
            mocked_log_cb,
            layer_information,
        )
        mocked_log_cb.assert_called()

    _assert_progress_report_values(
        mocked_progress_cb, total=layer_information.layers_total_size
    )

    mocked_progress_cb.reset_mock()
    mocked_log_cb.reset_mock()

    # check there were no warnings
    # NOTE: this would pop up in case docker changes its pulling statuses
    assert not [r.message for r in caplog.records if r.levelname == "WARNING"]

    # pull a second time should, the image is already there
    async with progress_bar.ProgressBarData(
        num_steps=layer_information.layers_total_size,
        progress_report_cb=mocked_progress_cb,
        progress_unit="Byte",
        description=faker.pystr(),
    ) as main_progress_bar:
        await pull_image(
            image,
            registry_settings,
            main_progress_bar,
            mocked_log_cb,
            layer_information,
        )
        mocked_log_cb.assert_called()
    assert (
        main_progress_bar._current_steps  # noqa: SLF001
        == layer_information.layers_total_size
    )
    _assert_progress_report_values(
        mocked_progress_cb, total=layer_information.layers_total_size
    )
    # check there were no warnings
    assert not [r.message for r in caplog.records if r.levelname == "WARNING"]


@pytest.mark.parametrize(
    "image",
    ["nginx:latest", "busybox:latest"],
)
async def test_pull_image_without_layer_information(
    remove_images_from_host: Callable[[list[str]], Awaitable[None]],
    image: DockerGenericTag,
    registry_settings: RegistrySettings,
    mocked_log_cb: mock.AsyncMock,
    mocked_progress_cb: mock.AsyncMock,
    caplog: pytest.LogCaptureFixture,
    faker: Faker,
):
    await remove_images_from_host([image])
    layer_information = await retrieve_image_layer_information(image, registry_settings)
    assert layer_information
    print(f"{image=} has {layer_information.layers_total_size=}")

    fake_number_of_steps = TypeAdapter(ByteSize).validate_python("200MiB")
    assert fake_number_of_steps > layer_information.layers_total_size
    async with progress_bar.ProgressBarData(
        num_steps=fake_number_of_steps,
        progress_report_cb=mocked_progress_cb,
        progress_unit="Byte",
        description=faker.pystr(),
    ) as main_progress_bar:
        await pull_image(
            image, registry_settings, main_progress_bar, mocked_log_cb, None
        )
        mocked_log_cb.assert_called()
        # depending on the system speed, and if the progress report callback is slow, then

    _assert_progress_report_values(mocked_progress_cb, total=fake_number_of_steps)
    mocked_progress_cb.reset_mock()
    mocked_log_cb.reset_mock()

    # check there were no warnings
    # NOTE: this would pop up in case docker changes its pulling statuses
    expected_warning = "pulling image without layer information"
    assert not [
        r.message
        for r in caplog.records
        if r.levelname == "WARNING" and not r.message.startswith(expected_warning)
    ]

    # pull a second time should, the image is already there, but the progress is then 0
    async with progress_bar.ProgressBarData(
        num_steps=1,
        progress_report_cb=mocked_progress_cb,
        progress_unit="Byte",
        description=faker.pystr(),
    ) as main_progress_bar:
        await pull_image(
            image, registry_settings, main_progress_bar, mocked_log_cb, None
        )
        mocked_log_cb.assert_called()
        assert main_progress_bar._current_steps == 0  # noqa: SLF001
    _assert_progress_report_values(mocked_progress_cb, total=1)
    # check there were no warnings
    assert not [
        r.message
        for r in caplog.records
        if r.levelname == "WARNING" and not r.message.startswith(expected_warning)
    ]


@pytest.mark.parametrize(
    "images_set",
    [
        {"itisfoundation/sleeper:1.0.0", "nginx:latest", "busybox:latest"},
    ],
)
async def test_pull_images_set(
    remove_images_from_host: Callable[[list[str]], Awaitable[None]],
    images_set: set[DockerGenericTag],
    registry_settings: RegistrySettings,
    mocked_log_cb: mock.AsyncMock,
    mocked_progress_cb: mock.AsyncMock,
    caplog: pytest.LogCaptureFixture,
):
    await remove_images_from_host(list(images_set))
    layer_informations = await asyncio.gather(
        *[
            retrieve_image_layer_information(image, registry_settings)
            for image in images_set
        ]
    )
    assert layer_informations
    images_total_size = sum(_.layers_total_size for _ in layer_informations if _)

    await pull_images(images_set, registry_settings, mocked_progress_cb, mocked_log_cb)
    mocked_log_cb.assert_called()
    _assert_progress_report_values(mocked_progress_cb, total=images_total_size)

    # check there were no warnings
    # NOTE: this would pop up in case docker changes its pulling statuses
    assert not [r.message for r in caplog.records if r.levelname == "WARNING"]

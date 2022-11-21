# pylint: disable=no-value-for-parameter
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from typing import Any, Awaitable, Callable, Iterator, Mapping
from unittest import mock

import aiodocker
import pytest
from fastapi import FastAPI
from pydantic import ByteSize, parse_obj_as
from pytest_mock.plugin import MockerFixture
from simcore_service_autoscaling.dynamic_scaling_core import check_dynamic_resources


@pytest.fixture
def disable_dynamic_service_background_task(mocker: MockerFixture) -> Iterator[None]:
    mocker.patch(
        "simcore_service_autoscaling.dynamic_scaling.start_background_task",
        autospec=True,
    )

    mocker.patch(
        "simcore_service_autoscaling.dynamic_scaling.stop_background_task",
        autospec=True,
    )

    yield


@pytest.fixture
def mock_start_aws_instance(mocker: MockerFixture) -> Iterator[mock.Mock]:
    mocked_start_aws_instance = mocker.patch(
        "simcore_service_autoscaling.dynamic_scaling_core.utils_aws.start_aws_instance",
        autospec=True,
    )
    yield mocked_start_aws_instance


@pytest.fixture
def minimal_configuration(
    docker_swarm: None,
    disable_dynamic_service_background_task: None,
    aws_subnet_id: str,
    aws_security_group_id: str,
    aws_ami_id: str,
) -> Iterator[None]:
    yield


async def test_check_dynamic_resources_with_no_services_does_nothing(
    minimal_configuration: None,
    initialized_app: FastAPI,
    mock_start_aws_instance: mock.Mock,
):
    await check_dynamic_resources(initialized_app)
    mock_start_aws_instance.assert_not_called()


async def test_check_dynamic_resources_with_service_with_too_much_resources_starts_nothing(
    minimal_configuration: None,
    async_docker_client: aiodocker.Docker,
    initialized_app: FastAPI,
    create_service: Callable[[dict[str, Any]], Awaitable[Mapping[str, Any]]],
    task_template: dict[str, Any],
    create_task_resources: Callable[[int, int], dict[str, Any]],
    assert_for_service_state: Callable[
        [aiodocker.Docker, Mapping[str, Any], list[str]], Awaitable[None]
    ],
    mock_start_aws_instance: mock.Mock,
):
    task_template_with_too_many_resource = task_template | create_task_resources(
        1000, 0
    )
    service_with_too_many_resources = await create_service(
        task_template_with_too_many_resource
    )
    await assert_for_service_state(
        async_docker_client,
        service_with_too_many_resources,
        ["pending"],
    )

    await check_dynamic_resources(initialized_app)
    mock_start_aws_instance.assert_not_called()


async def test_check_dynamic_resources_with_pending_resources_starts_r5n_4xlarge_instance(
    minimal_configuration: None,
    async_docker_client: aiodocker.Docker,
    initialized_app: FastAPI,
    create_service: Callable[[dict[str, Any]], Awaitable[Mapping[str, Any]]],
    task_template: dict[str, Any],
    create_task_resources: Callable[[int, int], dict[str, Any]],
    assert_for_service_state: Callable[
        [aiodocker.Docker, Mapping[str, Any], list[str]], Awaitable[None]
    ],
    mock_start_aws_instance: mock.Mock,
):
    task_template_for_r5n_4x_large_with_256Gib = task_template | create_task_resources(
        4, parse_obj_as(ByteSize, "128GiB")
    )
    service_with_too_many_resources = await create_service(
        task_template_for_r5n_4x_large_with_256Gib
    )
    await assert_for_service_state(
        async_docker_client,
        service_with_too_many_resources,
        ["pending"],
    )

    await check_dynamic_resources(initialized_app)
    mock_start_aws_instance.assert_called_once_with(
        initialized_app.state.settings.AUTOSCALING_AWS,
        instance_type="r5n.4xlarge",
        tags=mock.ANY,
    )


async def test_check_dynamic_resources_with_pending_resources_actually_starts_new_instances(
    minimal_configuration: None,
    async_docker_client: aiodocker.Docker,
    initialized_app: FastAPI,
    create_service: Callable[[dict[str, Any]], Awaitable[Mapping[str, Any]]],
    task_template: dict[str, Any],
    create_task_resources: Callable[[int, int], dict[str, Any]],
    assert_for_service_state: Callable[
        [aiodocker.Docker, Mapping[str, Any], list[str]], Awaitable[None]
    ],
):

    task_template_for_r5n_8x_large_with_256Gib = task_template | create_task_resources(
        4, parse_obj_as(ByteSize, "128GiB")
    )
    service_with_too_many_resources = await create_service(
        task_template_for_r5n_8x_large_with_256Gib
    )
    await assert_for_service_state(
        async_docker_client,
        service_with_too_many_resources,
        ["pending"],
    )

    await check_dynamic_resources(initialized_app)

    # check that the instances are really started

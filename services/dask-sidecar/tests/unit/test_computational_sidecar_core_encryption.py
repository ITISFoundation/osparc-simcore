# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument

from pathlib import Path

import pytest
from dask_task_models_library.container_tasks.docker import DockerBasicAuth
from dask_task_models_library.container_tasks.encryption import (
    JobEncryptionContext,
    TransferEncryptionSettings,
)
from dask_task_models_library.container_tasks.io import (
    TaskInputData,
    TaskOutputDataSchema,
)
from dask_task_models_library.container_tasks.protocol import (
    ContainerTaskParameters,
    TaskOwner,
)
from models_library.services_resources import BootMode
from packaging import version
from pydantic import AnyUrl, TypeAdapter
from pytest_mock import MockerFixture
from simcore_service_dask_sidecar.aes_gcm import generate_key
from simcore_service_dask_sidecar.computational_sidecar.core import ComputationalSidecar
from simcore_service_dask_sidecar.computational_sidecar.task_shared_volume import (
    TaskSharedVolumes,
)

_INTEGRATION_VERSION = version.Version("1.0.0")


@pytest.fixture
def job_encryption_context() -> JobEncryptionContext:
    return JobEncryptionContext(job_key=generate_key(), job_id="job-1")


@pytest.fixture
def task_volumes(tmp_path: Path) -> TaskSharedVolumes:
    return TaskSharedVolumes(tmp_path / "run")


def _create_sidecar(
    *,
    encryption: JobEncryptionContext | None,
    input_data: TaskInputData,
    output_data_keys: TaskOutputDataSchema,
    mocker: MockerFixture,
) -> ComputationalSidecar:
    task_parameters = ContainerTaskParameters(
        image="ubuntu",
        tag="latest",
        input_data=input_data,
        output_data_keys=output_data_keys,
        command=["run"],
        envs={},
        labels={},
        boot_mode=BootMode.CPU,
        task_owner=TaskOwner.model_validate(TaskOwner.model_json_schema()["examples"][0]),
    )
    return ComputationalSidecar(
        task_parameters=task_parameters,
        docker_auth=DockerBasicAuth.model_validate(DockerBasicAuth.model_json_schema()["examples"][0]),
        log_file_url=TypeAdapter(AnyUrl).validate_python("s3://bucket/logs.dat"),
        task_max_resources={},
        task_publishers=mocker.AsyncMock(),
        s3_settings=None,
        encryption=encryption,
    )


async def test_write_input_data_passes_per_file_encryption_settings(
    mocker: MockerFixture,
    task_volumes: TaskSharedVolumes,
    job_encryption_context: JobEncryptionContext,
):
    mocked_pull = mocker.patch(
        "simcore_service_dask_sidecar.computational_sidecar.core.pull_file_from_remote",
        autospec=True,
    )
    sidecar = _create_sidecar(
        encryption=job_encryption_context,
        input_data=TaskInputData.model_validate({"input_1": {"url": "s3://bucket/input_file.txt"}}),
        output_data_keys=TaskOutputDataSchema.model_validate({}),
        mocker=mocker,
    )

    await sidecar._write_input_data(task_volumes, _INTEGRATION_VERSION)  # noqa: SLF001

    mocked_pull.assert_called_once()
    encryption = mocked_pull.call_args.kwargs["encryption"]
    assert isinstance(encryption, TransferEncryptionSettings)
    assert encryption.file_id == "input_1"
    assert encryption.file_role == "input"
    assert encryption.job_id == job_encryption_context.job_id
    assert encryption.job_key.get_secret_value() == job_encryption_context.job_key.get_secret_value()


async def test_write_input_data_without_context_does_not_encrypt(
    mocker: MockerFixture,
    task_volumes: TaskSharedVolumes,
):
    mocked_pull = mocker.patch(
        "simcore_service_dask_sidecar.computational_sidecar.core.pull_file_from_remote",
        autospec=True,
    )
    sidecar = _create_sidecar(
        encryption=None,
        input_data=TaskInputData.model_validate({"input_1": {"url": "s3://bucket/input_file.txt"}}),
        output_data_keys=TaskOutputDataSchema.model_validate({}),
        mocker=mocker,
    )

    await sidecar._write_input_data(task_volumes, _INTEGRATION_VERSION)  # noqa: SLF001

    mocked_pull.assert_called_once()
    assert mocked_pull.call_args.kwargs["encryption"] is None


async def test_retrieve_output_data_passes_per_file_encryption_settings(
    mocker: MockerFixture,
    task_volumes: TaskSharedVolumes,
    job_encryption_context: JobEncryptionContext,
):
    mocked_push = mocker.patch(
        "simcore_service_dask_sidecar.computational_sidecar.core.push_file_to_remote",
        autospec=True,
    )
    (task_volumes.outputs_folder / "result.txt").write_text("output payload")
    sidecar = _create_sidecar(
        encryption=job_encryption_context,
        input_data=TaskInputData.model_validate({}),
        output_data_keys=TaskOutputDataSchema.model_validate(
            {
                "output_1": {
                    "required": True,
                    "mapping": "result.txt",
                    "url": "s3://bucket/result.txt",
                }
            }
        ),
        mocker=mocker,
    )

    await sidecar._retrieve_output_data(task_volumes, _INTEGRATION_VERSION)  # noqa: SLF001

    mocked_push.assert_called_once()
    encryption = mocked_push.call_args.kwargs["encryption"]
    assert isinstance(encryption, TransferEncryptionSettings)
    assert encryption.file_id == "output_1"
    assert encryption.file_role == "output"
    assert encryption.job_id == job_encryption_context.job_id
    assert encryption.job_key.get_secret_value() == job_encryption_context.job_key.get_secret_value()


async def test_retrieve_output_data_without_context_does_not_encrypt(
    mocker: MockerFixture,
    task_volumes: TaskSharedVolumes,
):
    mocked_push = mocker.patch(
        "simcore_service_dask_sidecar.computational_sidecar.core.push_file_to_remote",
        autospec=True,
    )
    (task_volumes.outputs_folder / "result.txt").write_text("output payload")
    sidecar = _create_sidecar(
        encryption=None,
        input_data=TaskInputData.model_validate({}),
        output_data_keys=TaskOutputDataSchema.model_validate(
            {
                "output_1": {
                    "required": True,
                    "mapping": "result.txt",
                    "url": "s3://bucket/result.txt",
                }
            }
        ),
        mocker=mocker,
    )

    await sidecar._retrieve_output_data(task_volumes, _INTEGRATION_VERSION)  # noqa: SLF001

    mocked_push.assert_called_once()
    assert mocked_push.call_args.kwargs["encryption"] is None

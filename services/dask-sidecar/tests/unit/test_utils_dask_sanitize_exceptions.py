# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import uuid

import pytest
from aws_library.kms import KMSKeyNotFoundError, KMSNotConnectedError
from dask_task_models_library.container_tasks.errors import ServiceEncryptionUnavailableError
from dask_task_models_library.container_tasks.io import TaskOutputData
from dask_task_models_library.container_tasks.protocol import (
    ContainerTaskParameters,
    TaskOwner,
)
from models_library.services_resources import BootMode
from simcore_service_dask_sidecar.errors import ConfigurationError, EncryptionNotConfiguredError
from simcore_service_dask_sidecar.utils.dask import sanitize_exceptions_across_dask_boundary

_TASK_OWNER = TaskOwner(
    user_id=1,
    project_id=uuid.uuid4(),
    node_id=uuid.uuid4(),
    parent_project_id=None,
    parent_node_id=None,
)

_TASK_PARAMETERS = ContainerTaskParameters(
    image="itisfoundation/sleeper",
    tag="2.1.2",
    input_data={},  # type: ignore[arg-type]
    output_data_keys={},  # type: ignore[arg-type]
    command=["/bin/bash", "-c", "echo 'should never run'"],
    envs={},
    labels={},
    task_owner=_TASK_OWNER,
    boot_mode=BootMode.CPU,
)


@pytest.mark.parametrize(
    "raised_exception",
    [
        EncryptionNotConfiguredError(msg="job requires decryption but DASK_SIDECAR_KMS is not configured"),
        KMSNotConnectedError(),
        KMSKeyNotFoundError(key_id="some-key-id"),
    ],
)
async def test_sanitize_exceptions_across_dask_boundary_translates_kms_errors(
    raised_exception: Exception,
):
    @sanitize_exceptions_across_dask_boundary
    async def _failing_func(*, task_parameters: ContainerTaskParameters) -> TaskOutputData:
        raise raised_exception

    with pytest.raises(ServiceEncryptionUnavailableError) as exc_info:
        await _failing_func(task_parameters=_TASK_PARAMETERS)

    # the original sidecar-internal/aws-library exception must not be chained
    # (it would not be importable/picklable on the dask client side)
    assert exc_info.value.__cause__ is None
    assert exc_info.value.__context__ is not None


async def test_sanitize_exceptions_across_dask_boundary_does_not_mistranslate_unrelated_configuration_errors():
    """Regression test: ConfigurationError is a generic base class also used for unrelated
    misconfiguration (e.g. RabbitMQ, see rabbitmq_worker_plugin.py). Only the KMS-specific
    EncryptionNotConfiguredError subclass must be translated into ServiceEncryptionUnavailableError
    - a bare/unrelated ConfigurationError must cross the dask boundary untouched.
    """

    @sanitize_exceptions_across_dask_boundary
    async def _failing_func(*, task_parameters: ContainerTaskParameters) -> TaskOutputData:
        raise ConfigurationError(msg="rabbitmq client is de-activated in this service settings")

    with pytest.raises(ConfigurationError) as exc_info:
        await _failing_func(task_parameters=_TASK_PARAMETERS)

    assert not isinstance(exc_info.value, EncryptionNotConfiguredError)

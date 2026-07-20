# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=no-member
# pylint: disable=too-many-arguments

import io
from collections.abc import Callable
from typing import Literal
from unittest import mock

import distributed
import fsspec
import pytest
from dask_task_models_library.container_tasks.docker import DockerBasicAuth
from dask_task_models_library.container_tasks.encryption import JobEncryptionContext
from dask_task_models_library.container_tasks.errors import ServiceEncryptionError
from dask_task_models_library.container_tasks.io import (
    FileUrl,
    TaskInputData,
    TaskOutputData,
    TaskOutputDataSchema,
)
from dask_task_models_library.container_tasks.protocol import (
    ContainerTaskParameters,
    TaskOwner,
)
from models_library.services_resources import BootMode
from pydantic import AnyUrl, SecretBytes, SecretStr, TypeAdapter
from pytest_simcore.helpers.dask_sidecar_tasks import (
    assert_expected_logs_published_to_rabbit,
)
from pytest_simcore.helpers.typing_env import EnvVarsDict
from settings_library.s3 import S3Settings
from simcore_service_dask_sidecar.utils.aes_gcm import (
    FORMAT_MAGIC,
    AesGcmStreamAuthError,
    decrypt_stream,
    encrypt_stream,
    generate_key,
)
from simcore_service_dask_sidecar.utils.files import (
    _s3fs_settings_from_s3_settings,
)
from simcore_service_dask_sidecar.worker import run_computational_sidecar

pytest_simcore_core_services_selection = [
    "rabbit",
]


def _encrypt_to_bytes(plaintext: bytes, *, root_key: bytes, file_id: str) -> bytes:
    encrypted = io.BytesIO()
    encrypt_stream(
        io.BytesIO(plaintext),
        encrypted,
        root_key=root_key,
        file_id=file_id,
    )
    return encrypted.getvalue()


def _decrypt_to_bytes(ciphertext: bytes, *, root_key: bytes, file_id: str) -> bytes:
    decrypted = io.BytesIO()
    decrypt_stream(
        io.BytesIO(ciphertext),
        decrypted,
        root_key=root_key,
        file_id=file_id,
    )
    return decrypted.getvalue()


@pytest.mark.parametrize(
    "integration_version, task_owner",
    [("1.0.0", "no_parent_node")],
    indirect=True,
)
async def test_run_computational_sidecar_with_encryption(
    app_environment: EnvVarsDict,
    mocked_get_image_labels: mock.Mock,
    s3_settings: S3Settings,
    s3_remote_file_url: Callable[..., AnyUrl],
    task_owner: TaskOwner,
    log_rabbit_client_parser: mock.AsyncMock,
    dask_client: distributed.Client,
):
    input_port_key = "input_file_1"
    output_port_key = "output_file_1"
    # the client encrypts with its own file_id, which deliberately differs from the port key
    client_input_file_id = "client-side-input-id-1"

    job_encryption_context = JobEncryptionContext(
        root_key=TypeAdapter(SecretBytes).validate_python(generate_key()),
        input_port_to_file_id={input_port_key: client_input_file_id},
    )
    root_key = job_encryption_context.root_key.get_secret_value()

    plaintext = b"this is the very secret payload that must travel encrypted\nline 2\n"
    computation_marker = "this was added during computation"
    expected_plaintext_output = plaintext + f"{computation_marker}\n".encode()

    # 1. upload an encrypted input file on S3 (as the client would do).
    #    NOTE: the client encrypts with its own file_id (which may differ from the port key);
    #    the sidecar uses the input_port_to_file_id mapping to derive the matching key.
    encrypted_input_url = s3_remote_file_url(file_path="encrypted_input.dat")
    s3_storage_kwargs = _s3fs_settings_from_s3_settings(s3_settings)
    with fsspec.open(f"{encrypted_input_url}", mode="wb", **s3_storage_kwargs) as fp:
        fp.write(  # type: ignore[attr-defined]
            _encrypt_to_bytes(
                plaintext,
                root_key=root_key,
                file_id=client_input_file_id,
            )
        )

    output_url = s3_remote_file_url(file_path="encrypted_output.dat")
    log_file_url = s3_remote_file_url(file_path="log.dat")
    log_transfer_settings = job_encryption_context.transfer_settings_for_logs()
    assert log_transfer_settings is not None

    # 2. run a task (through the dask subsystem) that copies the decrypted input to its
    #    output, appends some text and logs a marker line, with encryption enabled
    future = dask_client.submit(
        run_computational_sidecar,
        task_parameters=ContainerTaskParameters(
            image="itisfoundation/sleeper",
            tag="2.1.2",
            input_data=TaskInputData.model_validate(
                {input_port_key: FileUrl(url=encrypted_input_url, file_mapping="input.txt")}
            ),
            output_data_keys=TaskOutputDataSchema.model_validate(
                {
                    output_port_key: {
                        "required": True,
                        "mapping": "result.txt",
                        "url": f"{output_url}",
                    }
                }
            ),
            command=[
                "/bin/bash",
                "-c",
                " && ".join(
                    [
                        "cat ${INPUT_FOLDER}/input.txt > ${OUTPUT_FOLDER}/result.txt",
                        f"echo '{computation_marker}' >> ${{OUTPUT_FOLDER}}/result.txt",
                        f"echo '{computation_marker}'",
                    ]
                ),
            ],
            envs={},
            labels={},
            task_owner=task_owner,
            boot_mode=BootMode.CPU,
        ),
        docker_auth=DockerBasicAuth(server_address="docker.io", username="pytest", password=SecretStr("")),
        log_file_url=s3_remote_file_url(file_path="log.dat"),
        s3_settings=s3_settings,
        encryption=job_encryption_context,
        resources={},
    )

    output_data = future.result()
    assert isinstance(output_data, TaskOutputData), f"unexpected output data type: {output_data!r}"

    # 3. check the live logs (forwarded through RabbitMQ) contain the marker emitted by the task.
    #    NOTE: this is what we will need to keep working once logs themselves get encrypted.
    await assert_expected_logs_published_to_rabbit(
        log_rabbit_client_parser,
        [computation_marker],
        match="contains",
    )

    # 4. retrieve the encrypted output from S3
    assert output_port_key in output_data, (
        f"expected output '{output_port_key}' missing from {list(output_data.keys())}"
    )
    output_file = output_data[output_port_key]
    assert isinstance(output_file, FileUrl), f"expected a FileUrl output, got {output_file!r}"
    with fsspec.open(f"{output_file.url}", mode="rb", **s3_storage_kwargs) as fp:
        encrypted_output = fp.read()  # type: ignore[attr-defined]

    # the stored output is indeed encrypted (not plaintext)
    assert encrypted_output.startswith(FORMAT_MAGIC), "stored output does not look like an encrypted stream"
    assert expected_plaintext_output not in encrypted_output, "plaintext output leaked into the stored encrypted file"

    # 5. decrypt it with the per-output context and check we recover the expected payload,
    #    including the text added during the computation
    decrypted_output = _decrypt_to_bytes(
        encrypted_output,
        root_key=root_key,
        file_id=output_port_key,
    )
    assert decrypted_output == expected_plaintext_output, (
        f"decrypted output does not match expected payload.\n"
        f"got:      {decrypted_output!r}\n"
        f"expected: {expected_plaintext_output!r}"
    )
    assert computation_marker.encode() in decrypted_output, (
        f"text added during computation '{computation_marker}' missing from decrypted output"
    )
    mocked_get_image_labels.assert_called()

    # 6. check the log file on S3 is encrypted and can be decrypted with the correct key
    with fsspec.open(f"{log_file_url}", mode="rb", **s3_storage_kwargs) as fp:
        encrypted_log = fp.read()  # type: ignore[attr-defined]

    assert encrypted_log.startswith(FORMAT_MAGIC), "log file was not encrypted on S3"
    assert computation_marker.encode() not in encrypted_log, "log marker leaked as plaintext into the stored log file"

    decrypted_log = _decrypt_to_bytes(
        encrypted_log,
        root_key=root_key,
        file_id=log_transfer_settings.file_id,
    )
    assert computation_marker.encode() in decrypted_log

    # wrong key must raise an authentication error
    with pytest.raises(AesGcmStreamAuthError):
        _decrypt_to_bytes(
            encrypted_log,
            root_key=generate_key(),
            file_id=log_transfer_settings.file_id,
        )


@pytest.mark.parametrize(
    "integration_version, task_owner",
    [("1.0.0", "no_parent_node")],
    indirect=True,
)
@pytest.mark.parametrize(
    "wrong_field",
    ["root_key", "file_id"],
)
async def test_run_computational_sidecar_with_wrong_encryption_context_raises(
    wrong_field: Literal["root_key", "file_id"],
    app_environment: EnvVarsDict,
    mocked_get_image_labels: mock.Mock,
    s3_settings: S3Settings,
    s3_remote_file_url: Callable[..., AnyUrl],
    task_owner: TaskOwner,
    log_rabbit_client_parser: mock.AsyncMock,
    dask_client: distributed.Client,
):
    # the context the task will decrypt the input with
    input_port_key = "input_file_1"
    job_encryption_context = JobEncryptionContext(
        root_key=TypeAdapter(SecretBytes).validate_python(generate_key()),
        input_port_to_file_id={input_port_key: input_port_key},
    )
    plaintext = b"this is the very secret payload that must travel encrypted\n"

    # the context the client encrypts the input with: exactly ONE field is wrong, so that
    # the per-file key derived by the task (HKDF over root_key/file_id)
    # no longer matches and AES-GCM authentication must fail.
    encrypt_params: dict[str, str | bytes] = {
        "root_key": job_encryption_context.root_key.get_secret_value(),
        "file_id": input_port_key,
    }
    if wrong_field == "root_key":
        encrypt_params["root_key"] = generate_key()  # a different, unrelated key
    else:
        encrypt_params["file_id"] = "some-other-file-id"

    # 1. upload an encrypted input file on S3 using the WRONG context
    encrypted_input_url = s3_remote_file_url(file_path="encrypted_input.dat")
    s3_storage_kwargs = _s3fs_settings_from_s3_settings(s3_settings)
    with fsspec.open(f"{encrypted_input_url}", mode="wb", **s3_storage_kwargs) as fp:
        fp.write(  # type: ignore[attr-defined]
            _encrypt_to_bytes(
                plaintext,
                root_key=encrypt_params["root_key"],  # type: ignore[arg-type]
                file_id=encrypt_params["file_id"],  # type: ignore[arg-type]
            )
        )

    # 2. submit a task that tries to decrypt the input with the (correct) job context
    future = dask_client.submit(
        run_computational_sidecar,
        task_parameters=ContainerTaskParameters(
            image="itisfoundation/sleeper",
            tag="2.1.2",
            input_data=TaskInputData.model_validate(
                {input_port_key: FileUrl(url=encrypted_input_url, file_mapping="input.txt")}
            ),
            output_data_keys=TaskOutputDataSchema.model_validate({}),
            command=["/bin/bash", "-c", "echo 'should never run'"],
            envs={},
            labels={},
            task_owner=task_owner,
            boot_mode=BootMode.CPU,
        ),
        docker_auth=DockerBasicAuth(server_address="docker.io", username="pytest", password=SecretStr("")),
        log_file_url=s3_remote_file_url(file_path="log.dat"),
        s3_settings=s3_settings,
        encryption=job_encryption_context,
        resources={},
    )

    # 3. a clear, well-defined worker error must surface (decryption could not be authenticated).
    #    The low-level crypto error stays internal to the sidecar: it is not chained as cause
    #    (it is not importable on the dask client) but its message is embedded in the worker
    #    error so the failure remains diagnosable on the client side.
    with pytest.raises(ServiceEncryptionError) as exc_info:
        future.result()

    assert exc_info.value.code == "runtime.encryption"  # type: ignore[attr-defined]
    error_message = f"{exc_info.value}"
    assert "decrypt" in error_message
    assert input_port_key in error_message
    assert "authentication failed" in error_message
    assert exc_info.value.__cause__ is None, "the internal crypto error must not be chained across the dask boundary"

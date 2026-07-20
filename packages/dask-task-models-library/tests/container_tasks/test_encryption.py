import base64

import pytest
from dask_task_models_library.container_tasks.encryption import (
    JobEncryptionContext,
    ResolvedJobEncryptionContext,
    TransferEncryptionSettings,
)
from faker import Faker
from models_library.api_schemas_directorv2.encryption import (
    AES_256_GCM_KEY_SIZE_BYTES,
    KMS_CIPHERTEXT_MAX_BYTES,
    MAX_LP_STRING_BYTES,
    EncryptedRootKeyStr,
    JobEncryptionContextMetadata,
)
from models_library.projects_nodes_io import NodeID
from pydantic import SecretBytes, TypeAdapter, ValidationError


@pytest.mark.parametrize("model_cls", [ResolvedJobEncryptionContext, TransferEncryptionSettings])
@pytest.mark.parametrize("invalid_length", [AES_256_GCM_KEY_SIZE_BYTES - 1, AES_256_GCM_KEY_SIZE_BYTES + 1])
def test_root_key_must_have_exact_length(model_cls, invalid_length: int):
    example = model_cls.model_json_schema()["examples"][0]
    example["root_key"] = b"\x00" * invalid_length

    with pytest.raises(ValidationError):
        model_cls(**example)


def test_encrypted_root_key_must_not_exceed_max_ciphertext_size():
    TypeAdapter(EncryptedRootKeyStr).validate_python(base64.b64encode(b"0" * KMS_CIPHERTEXT_MAX_BYTES).decode())

    with pytest.raises(ValidationError):
        TypeAdapter(EncryptedRootKeyStr).validate_python(
            base64.b64encode(b"0" * (KMS_CIPHERTEXT_MAX_BYTES + 1)).decode()
        )


def test_file_id_must_not_be_empty():
    example = TransferEncryptionSettings.model_json_schema()["examples"][0]
    example["file_id"] = ""

    with pytest.raises(ValidationError):
        TransferEncryptionSettings(**example)


def test_file_id_must_not_exceed_max_length():
    example = TransferEncryptionSettings.model_json_schema()["examples"][0]

    example["file_id"] = "a" * MAX_LP_STRING_BYTES
    TransferEncryptionSettings(**example)  # max length is still valid

    example["file_id"] = "a" * (MAX_LP_STRING_BYTES + 1)
    with pytest.raises(ValidationError):
        TransferEncryptionSettings(**example)


def _encrypted_root_key(raw_ciphertext: bytes) -> EncryptedRootKeyStr:
    return TypeAdapter(EncryptedRootKeyStr).validate_python(base64.b64encode(raw_ciphertext).decode("ascii"))


def test_from_metadata_extracts_node_input_mapping(faker: Faker):
    fake_ciphertext = b"fake-kms-ciphertext"
    encrypted_node_id = NodeID(faker.uuid4())
    other_node_id = NodeID(faker.uuid4())
    metadata = JobEncryptionContextMetadata(
        encrypted_root_key=_encrypted_root_key(fake_ciphertext),
        input_port_to_file_id={
            encrypted_node_id: {"input_1": "input_1"},
            other_node_id: {"input_2": "some_file_id"},
        },
    )

    context = JobEncryptionContext.from_metadata(metadata, encrypted_node_id)
    assert base64.b64decode(context.encrypted_root_key.get_secret_value()) == fake_ciphertext
    assert context.input_port_to_file_id == {"input_1": "input_1"}


def test_from_metadata_node_without_encrypted_inputs(faker: Faker):
    fake_ciphertext = b"fake-kms-ciphertext"
    metadata = JobEncryptionContextMetadata(
        encrypted_root_key=_encrypted_root_key(fake_ciphertext),
        input_port_to_file_id={},
    )

    # a node with no encrypted inputs still gets a valid encrypted_root_key (to encrypt its outputs)
    context = JobEncryptionContext.from_metadata(metadata, NodeID(faker.uuid4()))
    assert base64.b64decode(context.encrypted_root_key.get_secret_value()) == fake_ciphertext
    assert context.input_port_to_file_id == {}


class _FakeKMSClient:
    """Test double for aws_library.kms.SimcoreKMSAPI - only implements decrypt()."""

    def __init__(self, plaintext: bytes) -> None:
        self.plaintext = plaintext
        self.calls: list[dict] = []

    async def decrypt(
        self,
        ciphertext: bytes,
        *,
        key_id: str | None = None,
        encryption_context: dict[str, str] | None = None,
    ) -> bytes:
        self.calls.append({"ciphertext": ciphertext, "key_id": key_id, "encryption_context": encryption_context})
        return self.plaintext


async def test_resolve_decrypts_ciphertext_into_plaintext_root_key():
    raw_root_key = b"0" * AES_256_GCM_KEY_SIZE_BYTES
    fake_ciphertext = b"fake-kms-ciphertext"
    context = JobEncryptionContext(
        encrypted_root_key=_encrypted_root_key(fake_ciphertext),
        input_port_to_file_id={"input_1": "file_1"},
    )
    kms_client = _FakeKMSClient(raw_root_key)

    resolved = await context.resolve(kms_client, key_id="some-key-id", encryption_context={"project_id": "abc"})

    assert isinstance(resolved, ResolvedJobEncryptionContext)
    assert resolved.root_key.get_secret_value() == raw_root_key
    assert resolved.input_port_to_file_id == {"input_1": "file_1"}
    assert kms_client.calls == [
        {"ciphertext": fake_ciphertext, "key_id": "some-key-id", "encryption_context": {"project_id": "abc"}}
    ]


def test_transfer_settings_for_input_returns_settings_for_encrypted_input():
    root_key = b"0" * AES_256_GCM_KEY_SIZE_BYTES
    context = ResolvedJobEncryptionContext(
        root_key=TypeAdapter(SecretBytes).validate_python(root_key),
        input_port_to_file_id={"input_1": "file_1"},
    )

    settings = context.transfer_settings_for_input("input_1")

    assert settings == TransferEncryptionSettings(
        root_key=TypeAdapter(SecretBytes).validate_python(root_key), file_id="file_1"
    )


def test_transfer_settings_for_input_returns_none_for_unencrypted_input():
    context = ResolvedJobEncryptionContext(
        root_key=TypeAdapter(SecretBytes).validate_python(b"0" * AES_256_GCM_KEY_SIZE_BYTES),
        input_port_to_file_id={"input_1": "file_1"},
    )

    settings = context.transfer_settings_for_input("missing_input")

    assert settings is None


def test_transfer_settings_for_output_uses_output_key_as_file_id():
    root_key = b"0" * AES_256_GCM_KEY_SIZE_BYTES
    context = ResolvedJobEncryptionContext(
        root_key=TypeAdapter(SecretBytes).validate_python(root_key), input_port_to_file_id={}
    )

    settings = context.transfer_settings_for_output("output_1")

    assert settings == TransferEncryptionSettings(
        root_key=TypeAdapter(SecretBytes).validate_python(root_key), file_id="output_1"
    )


def test_transfer_settings_for_logs_uses_fixed_logs_file_id_when_inputs_are_encrypted():
    root_key = b"0" * AES_256_GCM_KEY_SIZE_BYTES
    context = ResolvedJobEncryptionContext(
        root_key=TypeAdapter(SecretBytes).validate_python(root_key),
        input_port_to_file_id={"input_1": "file_1"},
    )

    settings = context.transfer_settings_for_logs()

    assert settings == TransferEncryptionSettings(
        root_key=TypeAdapter(SecretBytes).validate_python(root_key), file_id="service-logs"
    )

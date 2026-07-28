import base64

import pytest
from dask_task_models_library.container_tasks.encryption import (
    JobEncryptionContext,
)
from faker import Faker
from models_library.api_schemas_directorv2.encryption import (
    KMS_CIPHERTEXT_MAX_BYTES,
    EncryptedRootKeyStr,
    JobEncryptionContextMetadata,
)
from models_library.projects_nodes_io import NodeID
from pydantic import TypeAdapter, ValidationError


def test_encrypted_root_key_must_not_exceed_max_ciphertext_size():
    TypeAdapter(EncryptedRootKeyStr).validate_python(base64.b64encode(b"0" * KMS_CIPHERTEXT_MAX_BYTES).decode())

    with pytest.raises(ValidationError):
        TypeAdapter(EncryptedRootKeyStr).validate_python(
            base64.b64encode(b"0" * (KMS_CIPHERTEXT_MAX_BYTES + 1)).decode()
        )


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

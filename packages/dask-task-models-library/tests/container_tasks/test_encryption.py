import base64

import pytest
from dask_task_models_library.container_tasks.encryption import (
    KEY_SIZE_BYTES,
    JobEncryptionContext,
    TransferEncryptionSettings,
)
from faker import Faker
from models_library.api_schemas_directorv2.encryption import (
    JobEncryptionContextMetadata,
)
from models_library.projects_nodes_io import NodeID
from pydantic import ValidationError


@pytest.mark.parametrize("model_cls", [JobEncryptionContext, TransferEncryptionSettings])
@pytest.mark.parametrize("invalid_length", [KEY_SIZE_BYTES - 1, KEY_SIZE_BYTES + 1])
def test_root_key_must_have_exact_length(model_cls, invalid_length: int):
    example = model_cls.model_json_schema()["examples"][0]
    example["root_key"] = b"\x00" * invalid_length

    with pytest.raises(ValidationError):
        model_cls(**example)


def test_from_metadata_extracts_node_input_mapping(faker: Faker):
    raw_root_key = b"0" * KEY_SIZE_BYTES
    encrypted_node_id = NodeID(faker.uuid4())
    other_node_id = NodeID(faker.uuid4())
    metadata = JobEncryptionContextMetadata(
        root_key=base64.b64encode(raw_root_key).decode("ascii"),  # type: ignore[arg-type]
        input_port_to_file_id={
            encrypted_node_id: {"input_1": "input_1"},
            other_node_id: {"input_2": "some_file_id"},
        },
    )

    context = JobEncryptionContext.from_metadata(metadata, encrypted_node_id)
    assert context.root_key.get_secret_value() == raw_root_key
    assert context.input_port_to_file_id == {"input_1": "input_1"}


def test_from_metadata_node_without_encrypted_inputs(faker: Faker):
    raw_root_key = b"0" * KEY_SIZE_BYTES
    metadata = JobEncryptionContextMetadata(
        root_key=base64.b64encode(raw_root_key).decode("ascii"),  # type: ignore[arg-type]
        input_port_to_file_id={},
    )

    # a node with no encrypted inputs still gets a valid root_key (to encrypt its outputs)
    context = JobEncryptionContext.from_metadata(metadata, NodeID(faker.uuid4()))
    assert context.root_key.get_secret_value() == raw_root_key
    assert context.input_port_to_file_id == {}

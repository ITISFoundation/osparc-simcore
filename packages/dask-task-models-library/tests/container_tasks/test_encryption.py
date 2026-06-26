import pytest
from dask_task_models_library.container_tasks.encryption import (
    KEY_SIZE_BYTES,
    JobEncryptionContext,
    TransferEncryptionSettings,
)
from pydantic import ValidationError


@pytest.mark.parametrize("model_cls", [JobEncryptionContext, TransferEncryptionSettings])
@pytest.mark.parametrize("invalid_length", [KEY_SIZE_BYTES - 1, KEY_SIZE_BYTES + 1])
def test_root_key_must_have_exact_length(model_cls, invalid_length: int):
    example = model_cls.model_json_schema()["examples"][0]
    example["root_key"] = b"\x00" * invalid_length

    with pytest.raises(ValidationError):
        model_cls(**example)

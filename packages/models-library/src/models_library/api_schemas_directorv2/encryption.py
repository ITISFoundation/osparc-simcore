import base64
import binascii
from typing import Annotated, Final

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator
from pydantic.config import JsonDict

from ..projects_nodes_io import NodeID

# Mirrors dask_task_models_library.container_tasks.encryption (simcore-aesgcm-stream-v1).
AES_256_GCM_KEY_SIZE_BYTES: Final[int] = 32  # AES-256 root key length

type FileIDStr = str  # client-chosen file identifier mixed into HKDF key derivation

_ROOT_KEY_EXAMPLE: Final[str] = "0123456789abcdef0123456789abcdef"
_NODE_ID_EXAMPLE: Final[str] = "3fa85f64-5717-4562-b3fc-2c963f66afa6"


class JobEncryptionContextMetadata(BaseModel):
    root_key: Annotated[
        SecretStr,
        Field(description="base64-encoded 32-byte root key shared by all tasks of the job"),
    ]
    input_port_to_file_id: Annotated[
        dict[NodeID, dict[str, FileIDStr]],
        Field(
            default_factory=dict,
            description=(
                "Per computational node, maps each encrypted input port key to the file_id the client "
                "used to derive its key (may differ from the port key). Only listed inputs are decrypted."
            ),
        ),
    ]

    @field_validator("root_key")
    @classmethod
    def _validate_root_key_is_base64_of_expected_size(cls, value: SecretStr) -> SecretStr:
        try:
            raw = base64.b64decode(value.get_secret_value(), validate=True)
        except binascii.Error as err:
            msg = "root_key must be valid base64"
            raise ValueError(msg) from err
        if len(raw) != AES_256_GCM_KEY_SIZE_BYTES:
            msg = f"root_key must decode to {AES_256_GCM_KEY_SIZE_BYTES} bytes, got {len(raw)}"
            raise ValueError(msg)
        return value

    @staticmethod
    def _update_json_schema_extra(schema: JsonDict) -> None:
        schema.update(
            {
                "examples": [
                    {
                        "root_key": base64.b64encode(_ROOT_KEY_EXAMPLE.encode("ascii")).decode("ascii"),
                        "input_port_to_file_id": {_NODE_ID_EXAMPLE: {"input_1": "input_1"}},
                    },
                ]
            }
        )

    model_config = ConfigDict(
        frozen=True,
        json_schema_extra=_update_json_schema_extra,
    )

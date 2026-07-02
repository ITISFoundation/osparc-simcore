import base64
import binascii
from typing import Annotated, Final

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, SecretStr, StringConstraints
from pydantic.config import JsonDict

from ..projects_nodes_io import NodeID

# Mirrors dask_task_models_library.container_tasks.encryption (simcore-aesgcm-stream-v1).
AES_256_GCM_KEY_SIZE_BYTES: Final[int] = 32  # AES-256 root key length

# Matches the uint16 length-prefix (lp()) limit enforced on file_id by the aesgcm-stream-v1
# protocol (services/dask-sidecar utils/aes_gcm.py _MAX_LP_STRING_BYTES); that limit is on the
# UTF-8 encoded byte length, which equals the character count for the plain ASCII identifiers
# used in practice (port keys / client file ids).
MAX_FILE_ID_LENGTH: Final[int] = 0xFFFF

# client-chosen file identifier mixed into HKDF key derivation
type FileIDStr = Annotated[str, StringConstraints(min_length=1, max_length=MAX_FILE_ID_LENGTH)]


def _validate_root_key_is_base64_of_expected_size(value: SecretStr) -> SecretStr:
    try:
        raw = base64.b64decode(value.get_secret_value(), validate=True)
    except binascii.Error as err:
        msg = "root_key must be valid base64"
        raise ValueError(msg) from err
    if len(raw) != AES_256_GCM_KEY_SIZE_BYTES:
        msg = f"root_key must decode to {AES_256_GCM_KEY_SIZE_BYTES} bytes, got {len(raw)}"
        raise ValueError(msg)
    return value


# base64-encoded 32-byte root key shared by all tasks of the job (single source of truth for
# the constraint, reused wherever a client supplies a root_key, e.g. api-server's JobEncryptionInputs)
type RootKeyStr = Annotated[
    SecretStr,
    AfterValidator(_validate_root_key_is_base64_of_expected_size),
    Field(description="base64-encoded 32-byte root key shared by all tasks of the job"),
]

_ROOT_KEY_EXAMPLE: Final[str] = "0123456789abcdef0123456789abcdef"
_NODE_ID_EXAMPLE: Final[str] = "3fa85f64-5717-4562-b3fc-2c963f66afa6"


class JobEncryptionContextMetadata(BaseModel):
    root_key: RootKeyStr
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

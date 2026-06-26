from typing import Annotated, Final

from pydantic import BaseModel, ConfigDict, Field, SecretBytes
from pydantic.config import JsonDict

KEY_SIZE_BYTES: Final[int] = 32  # AES-256 root key length (simcore-aesgcm-stream-v1)

_ROOT_KEY_EXAMPLE: Final[str] = "0123456789abcdef0123456789abcdef"


_RootKeyType = Annotated[
    SecretBytes,
    Field(
        min_length=KEY_SIZE_BYTES,
        max_length=KEY_SIZE_BYTES,
        description="Secret root key used to derive every per-file key (HKDF over root_key/file_id)",
    ),
]


class JobEncryptionContext(BaseModel):
    root_key: _RootKeyType
    input_port_to_file_id: Annotated[
        dict[str, str],
        Field(
            description=(
                "Maps each encrypted input port key to the file_id the client used to derive its key "
                "(may differ from the port key). Only listed inputs are decrypted."
            ),
        ),
    ]

    @staticmethod
    def _update_json_schema_extra(schema: JsonDict) -> None:
        schema.update(
            {
                "examples": [
                    {
                        "root_key": _ROOT_KEY_EXAMPLE,
                        "input_port_to_file_id": {"input_1": "input_1"},
                    },
                ]
            }
        )

    model_config = ConfigDict(
        frozen=True,
        json_schema_extra=_update_json_schema_extra,
    )


class TransferEncryptionSettings(BaseModel):
    root_key: _RootKeyType
    file_id: Annotated[
        str,
        Field(description="Per-file identifier mixed into key derivation"),
    ]

    @staticmethod
    def _update_json_schema_extra(schema: JsonDict) -> None:
        schema.update(
            {
                "examples": [
                    {
                        "root_key": _ROOT_KEY_EXAMPLE,
                        "file_id": "input_1",
                    },
                ]
            }
        )

    model_config = ConfigDict(
        frozen=True,
        json_schema_extra=_update_json_schema_extra,
    )

import base64
from typing import Annotated, Final

from models_library.api_schemas_directorv2.encryption import (
    JobEncryptionContextMetadata,
)
from models_library.projects_nodes_io import NodeID
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

    @classmethod
    def from_metadata(cls, metadata: JobEncryptionContextMetadata, node_id: NodeID) -> "JobEncryptionContext":
        """Builds the per-task context for ``node_id`` from the REST/storage transport form.

        The shared base64 ``root_key`` is decoded back into raw bytes and only the input mapping
        of the given node is kept (empty when the node has no encrypted inputs).
        """
        return cls(
            root_key=SecretBytes(base64.b64decode(metadata.root_key.get_secret_value())),
            input_port_to_file_id=metadata.input_port_to_file_id.get(node_id, {}),
        )

    def transfer_settings_for_input(self, input_key: str) -> "TransferEncryptionSettings | None":
        """Returns the per-file transfer settings for an input port, or None when that port is not encrypted."""
        file_id = self.input_port_to_file_id.get(input_key)
        if file_id is None:
            return None
        return TransferEncryptionSettings(root_key=self.root_key, file_id=file_id)

    def transfer_settings_for_output(self, output_key: str) -> "TransferEncryptionSettings":
        """Returns the per-file transfer settings for an output (the file_id is the output key)."""
        return TransferEncryptionSettings(root_key=self.root_key, file_id=output_key)

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

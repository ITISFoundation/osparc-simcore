import base64
from typing import Annotated, Final, Protocol, Self

from models_library.api_schemas_directorv2.encryption import (
    AES_256_GCM_KEY_SIZE_BYTES,
    EncryptedRootKeyStr,
    FileIDStr,
    JobEncryptionContextMetadata,
)
from models_library.projects_nodes_io import NodeID
from pydantic import BaseModel, ConfigDict, Field, SecretBytes
from pydantic.config import JsonDict

_SIDECAR_LOGS_FILE_ID: Final[str] = "service-logs"
_ROOT_KEY_EXAMPLE: Final[str] = "0123456789abcdef0123456789abcdef"
_ENCRYPTED_ROOT_KEY_EXAMPLE: Final[str] = "fake-kms-ciphertext-blob"


type _RootKeySecretBytes = Annotated[
    SecretBytes,
    Field(
        min_length=AES_256_GCM_KEY_SIZE_BYTES,
        max_length=AES_256_GCM_KEY_SIZE_BYTES,
        description="Secret root key used to derive every per-file key (HKDF over root_key/file_id)",
    ),
]


class SupportsKMSDecrypt(Protocol):
    """Structural type satisfied by ``aws_library.kms.SimcoreKMSAPI`` (and test doubles).

    NOTE: this package purposely does NOT depend on aws-library - it only describes the
    shape of the client required to resolve a :class:`JobEncryptionContext`.
    """

    async def decrypt(
        self,
        ciphertext: bytes,
        *,
        key_id: str | None = None,
        encryption_context: dict[str, str] | None = None,
    ) -> bytes: ...


class TransferEncryptionSettings(BaseModel):
    root_key: _RootKeySecretBytes
    file_id: Annotated[
        FileIDStr,
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


class ResolvedJobEncryptionContext(BaseModel):
    """The in-memory, plaintext form of the job's encryption context.

    NOTE: this must only ever be constructed inside the trusted, ephemeral task execution
    environment (i.e. the dask-sidecar worker), by resolving a :class:`JobEncryptionContext`
    via :meth:`JobEncryptionContext.resolve`. It must never be pickled/sent over the network
    nor persisted.
    """

    root_key: _RootKeySecretBytes
    input_port_to_file_id: Annotated[
        dict[str, FileIDStr],
        Field(
            description=(
                "Maps each encrypted input port key to the file_id the client used to derive its key "
                "(may differ from the port key). Only listed inputs are decrypted."
            ),
        ),
    ]

    def transfer_settings_for_input(self, input_key: str) -> TransferEncryptionSettings | None:
        """Returns the per-file transfer settings for an input port, or None when that port is not encrypted."""
        file_id = self.input_port_to_file_id.get(input_key)
        if file_id is None:
            return None
        return TransferEncryptionSettings(root_key=self.root_key, file_id=file_id)

    def transfer_settings_for_output(self, output_key: str) -> TransferEncryptionSettings:
        """Returns the per-file transfer settings for an output (the file_id is the output key)."""
        return TransferEncryptionSettings(root_key=self.root_key, file_id=output_key)

    def transfer_settings_for_logs(self) -> TransferEncryptionSettings | None:
        """Returns the per-file transfer settings for the logs (the file_id is fixed)."""
        return TransferEncryptionSettings(root_key=self.root_key, file_id=_SIDECAR_LOGS_FILE_ID)

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


class JobEncryptionContext(BaseModel):
    """The wire form of the job's encryption context: carries the AWS KMS-encrypted root key
    (never plaintext) from director-v2 down to the dask-sidecar worker.

    Only :meth:`resolve` ever turns this into plaintext, and it must only be called inside the
    dask-sidecar worker process, right before the root key is needed to encrypt/decrypt files.
    """

    encrypted_root_key: EncryptedRootKeyStr
    input_port_to_file_id: Annotated[
        dict[str, FileIDStr],
        Field(
            description=(
                "Maps each encrypted input port key to the file_id the client used to derive its key "
                "(may differ from the port key). Only listed inputs are decrypted."
            ),
        ),
    ]

    @classmethod
    def from_metadata(cls, metadata: JobEncryptionContextMetadata, node_id: NodeID) -> Self:
        """Builds the per-task wire-form context for ``node_id`` from the REST/storage transport form.

        NOTE: no cryptographic operation happens here - the root key stays an opaque KMS
        ciphertext blob. Only the per-node input mapping is sliced out (empty when the node
        has no encrypted inputs).
        """
        return cls(
            encrypted_root_key=metadata.encrypted_root_key,
            input_port_to_file_id=metadata.input_port_to_file_id.get(NodeID(f"{node_id}"), {}),
        )

    async def resolve(
        self,
        kms_client: SupportsKMSDecrypt,
        *,
        key_id: str | None = None,
        encryption_context: dict[str, str] | None = None,
    ) -> ResolvedJobEncryptionContext:
        """Decrypts the KMS ciphertext into the plaintext root key.

        NOTE: this must only be called inside the dask-sidecar worker process - the resulting
        plaintext must never leave that process (no pickling to other dask workers, no logging,
        no persistence).
        """
        ciphertext = base64.b64decode(self.encrypted_root_key.get_secret_value())
        plaintext = await kms_client.decrypt(ciphertext, key_id=key_id, encryption_context=encryption_context)
        return ResolvedJobEncryptionContext(
            root_key=SecretBytes(plaintext),
            input_port_to_file_id=self.input_port_to_file_id,
        )

    @staticmethod
    def _update_json_schema_extra(schema: JsonDict) -> None:
        schema.update(
            {
                "examples": [
                    {
                        "encrypted_root_key": base64.b64encode(_ENCRYPTED_ROOT_KEY_EXAMPLE.encode("ascii")).decode(
                            "ascii"
                        ),
                        "input_port_to_file_id": {"input_1": "input_1"},
                    },
                ]
            }
        )

    model_config = ConfigDict(
        frozen=True,
        json_schema_extra=_update_json_schema_extra,
    )

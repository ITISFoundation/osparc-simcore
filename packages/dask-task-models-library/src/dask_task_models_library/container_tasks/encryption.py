import base64
from typing import Annotated, Final, Protocol, Self

from models_library.api_schemas_directorv2.encryption import (
    EncryptedRootKeyStr,
    FileIDStr,
    JobEncryptionContextMetadata,
)
from models_library.projects_nodes_io import NodeID
from pydantic import BaseModel, ConfigDict, Field
from pydantic.config import JsonDict

_ENCRYPTED_ROOT_KEY_EXAMPLE: Final[str] = "fake-kms-ciphertext-blob"


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


class JobEncryptionContext(BaseModel):
    """The wire form of the job's encryption context: carries the AWS KMS-encrypted root key
    (never plaintext) from director-v2 down to the dask-sidecar worker.

    NOTE: only the dask-sidecar worker ever turns this into plaintext, via
    ``simcore_service_dask_sidecar.utils.encryption.resolve_job_encryption_context``, and only
    right before the root key is needed to encrypt/decrypt files.
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

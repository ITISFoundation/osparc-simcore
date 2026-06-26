"""Encryption transport models shared across dask computational tasks.

These pydantic models define the cross-service contract for end-to-end file encryption
(see the ``simcore-aesgcm-stream-v1`` protocol in the dask-sidecar). They carry the
secret material and context needed by the dask-sidecar to derive per-file keys.

The job-level :class:`JobEncryptionContext` is meant to be transported as a separate
``client.submit(..., encryption=...)`` kwarg (mirroring ``S3Settings``), and must never
be embedded in the persisted ``ContainerTaskParameters``.

The ``root_key`` is a :class:`~pydantic.SecretBytes`: it is masked in ``repr``/``str`` and
``model_dump_json`` (shown as ``**********``), so logging a model never leaks the secret.
Use ``root_key.get_secret_value()`` to access the raw bytes for key derivation.
"""

from typing import Annotated, Final

from pydantic import BaseModel, ConfigDict, Field, SecretBytes
from pydantic.config import JsonDict

KEY_SIZE_BYTES: Final[int] = 32  # AES-256 root key length (simcore-aesgcm-stream-v1)

_ROOT_KEY_EXAMPLE: Final[str] = "0123456789abcdef0123456789abcdef"


class JobEncryptionContext(BaseModel):
    """Job-level encryption secret and context.

    Transported as a separate dask submit kwarg (like ``S3Settings``). Per-file keys are
    derived locally by combining this context with each port's ``file_id``.
    """

    root_key: Annotated[
        SecretBytes,
        Field(
            min_length=KEY_SIZE_BYTES,
            max_length=KEY_SIZE_BYTES,
            description="Secret root key used to derive every per-file key (HKDF over root_key/file_id)",
        ),
    ]
    input_port_to_file_id: Annotated[
        dict[str, str],
        Field(
            description=(
                "Maps each encrypted input port key to the file_id the client used to derive its key "
                "(may differ from the port key). Only listed inputs are decrypted; the rest are "
                "downloaded as plaintext. Outputs are always encrypted using the output port key as file_id"
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
    """Per-file encryption settings used by the sidecar to derive a single file key."""

    root_key: Annotated[
        SecretBytes,
        Field(
            min_length=KEY_SIZE_BYTES,
            max_length=KEY_SIZE_BYTES,
            description="Secret root key used to derive the per-file key",
        ),
    ]
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

"""Encryption transport models shared across dask computational tasks.

These pydantic models define the cross-service contract for end-to-end file encryption
(see the ``simcore-aesgcm-stream-v1`` protocol in the dask-sidecar). They carry the
secret material and context needed by the dask-sidecar to derive per-file keys.

The job-level :class:`JobEncryptionContext` is meant to be transported as a separate
``client.submit(..., encryption=...)`` kwarg (mirroring ``S3Settings``), and must never
be embedded in the persisted ``ContainerTaskParameters``.
"""

from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.config import JsonDict

KEY_SIZE_BYTES: Final[int] = 32  # AES-256 job key length (simcore-aesgcm-stream-v1)
MAX_JOB_ID_LENGTH: Final[int] = 0xFFFF  # protocol cap; sidecar enforces UTF-8 byte bound

_JOB_KEY_EXAMPLE: Final[bytes] = b"0123456789abcdef0123456789abcdef"
_JOB_ID_EXAMPLE: Final[str] = "correct-horse-battery-staple"


class JobEncryptionContext(BaseModel):
    """Job-level encryption secret and context.

    Transported as a separate dask submit kwarg (like ``S3Settings``). When present, the
    sidecar encrypts/decrypts *all* file ports (all-or-nothing). Per-file keys are derived
    locally by combining this context with each port's ``file_id``/``file_role``.
    """

    job_key: bytes = Field(min_length=KEY_SIZE_BYTES, max_length=KEY_SIZE_BYTES)
    job_id: str = Field(min_length=1, max_length=MAX_JOB_ID_LENGTH)

    @staticmethod
    def _update_json_schema_extra(schema: JsonDict) -> None:
        schema.update(
            {
                "examples": [
                    {
                        "job_key": _JOB_KEY_EXAMPLE,
                        "job_id": _JOB_ID_EXAMPLE,
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

    job_key: bytes = Field(min_length=KEY_SIZE_BYTES, max_length=KEY_SIZE_BYTES)
    job_id: str = Field(min_length=1, max_length=MAX_JOB_ID_LENGTH)
    file_id: str
    file_role: Literal["input", "output"]

    @staticmethod
    def _update_json_schema_extra(schema: JsonDict) -> None:
        schema.update(
            {
                "examples": [
                    {
                        "job_key": _JOB_KEY_EXAMPLE,
                        "job_id": _JOB_ID_EXAMPLE,
                        "file_id": "input_1",
                        "file_role": "input",
                    },
                ]
            }
        )

    model_config = ConfigDict(
        frozen=True,
        json_schema_extra=_update_json_schema_extra,
    )

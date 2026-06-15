from __future__ import annotations

import base64
import os
import struct
from pathlib import Path
from typing import Annotated, Final

from annotated_types import doc
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

KEY_SIZE_BYTES: Final[int] = 32
NONCE_SIZE_BYTES: Final[int] = 12
FORMAT_MAGIC: Final[bytes] = b"SIMCOREAESGCM"
FORMAT_VERSION: Final[int] = 1
# Envelope header structure: 13-byte simcore magic (SIMCOREAESGCM) + 1-byte format version + 12-byte per-message salt
_ENVELOPE_HEADER_STRUCT: Final[struct.Struct] = struct.Struct(">13sB12s")

type UrlSafeBase64Text = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1),
]


def _xor_nonce(base_nonce: bytes, salt: bytes) -> bytes:
    return bytes(a ^ b for a, b in zip(base_nonce, salt, strict=True))


def _urlsafe_b64_decode_exact(
    raw_value: Annotated[UrlSafeBase64Text, doc("Encoded key or nonce value")],
    *,
    expected_len: Annotated[int, doc("Exact number of decoded bytes")],
    value_name: str,
) -> bytes:
    try:
        decoded = base64.urlsafe_b64decode(raw_value.encode("ascii"))
    except ValueError as error:
        msg = f"Invalid {value_name}: expected URL-safe base64 text"
        raise ValueError(msg) from error

    if len(decoded) != expected_len:
        msg = f"Invalid {value_name}: expected {expected_len} bytes, got {len(decoded)}"
        raise ValueError(msg)
    return decoded


def _urlsafe_b64_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii")


def generate_key() -> bytes:
    return os.urandom(KEY_SIZE_BYTES)


def generate_base_nonce() -> bytes:
    return os.urandom(NONCE_SIZE_BYTES)


def generate_key_b64() -> str:
    return _urlsafe_b64_encode(generate_key())


def generate_base_nonce_b64() -> str:
    return _urlsafe_b64_encode(generate_base_nonce())


class AesGcmMaterial(BaseModel):
    """Validated AES-GCM material for reusable encryption operations."""

    model_config = ConfigDict(frozen=True)

    key: bytes = Field(min_length=KEY_SIZE_BYTES, max_length=KEY_SIZE_BYTES, repr=False)
    base_nonce: bytes = Field(
        min_length=NONCE_SIZE_BYTES,
        max_length=NONCE_SIZE_BYTES,
        repr=False,
    )

    @classmethod
    def create(cls) -> AesGcmMaterial:
        return cls(key=generate_key(), base_nonce=generate_base_nonce())

    @classmethod
    def from_base64(
        cls,
        key_b64: Annotated[UrlSafeBase64Text, doc("URL-safe base64 encoded 32-byte key")],
        base_nonce_b64: Annotated[
            UrlSafeBase64Text,
            doc("URL-safe base64 encoded 12-byte base nonce"),
        ],
    ) -> AesGcmMaterial:
        return cls(
            key=_urlsafe_b64_decode_exact(
                key_b64,
                expected_len=KEY_SIZE_BYTES,
                value_name="AES-GCM key",
            ),
            base_nonce=_urlsafe_b64_decode_exact(
                base_nonce_b64,
                expected_len=NONCE_SIZE_BYTES,
                value_name="AES-GCM base nonce",
            ),
        )

    def key_b64(self) -> str:
        return _urlsafe_b64_encode(self.key)

    def base_nonce_b64(self) -> str:
        return _urlsafe_b64_encode(self.base_nonce)


def encrypt_bytes(
    plaintext: bytes,
    material: AesGcmMaterial,
    *,
    associated_data: bytes | None = None,
) -> bytes:
    salt = os.urandom(NONCE_SIZE_BYTES)
    nonce = _xor_nonce(material.base_nonce, salt)
    encrypted = AESGCM(material.key).encrypt(nonce, plaintext, associated_data)
    return _ENVELOPE_HEADER_STRUCT.pack(FORMAT_MAGIC, FORMAT_VERSION, salt) + encrypted


def decrypt_bytes(
    encrypted_payload: bytes,
    material: AesGcmMaterial,
    *,
    associated_data: bytes | None = None,
) -> bytes:
    if len(encrypted_payload) < _ENVELOPE_HEADER_STRUCT.size + 16:
        msg = "Encrypted payload is too short"
        raise ValueError(msg)

    header = encrypted_payload[: _ENVELOPE_HEADER_STRUCT.size]
    ciphertext_and_tag = encrypted_payload[_ENVELOPE_HEADER_STRUCT.size :]

    magic, version, salt = _ENVELOPE_HEADER_STRUCT.unpack(header)
    if magic != FORMAT_MAGIC:
        msg = "Invalid AES-GCM payload header"
        raise ValueError(msg)
    if version != FORMAT_VERSION:
        msg = f"Unsupported AES-GCM payload version: {version}"
        raise ValueError(msg)

    nonce = _xor_nonce(material.base_nonce, salt)
    try:
        return AESGCM(material.key).decrypt(nonce, ciphertext_and_tag, associated_data)
    except InvalidTag as error:
        msg = "AES-GCM authentication failed"
        raise ValueError(msg) from error


def encrypt_string(
    plaintext: Annotated[str, doc("String to encrypt")],
    material: AesGcmMaterial,
    *,
    encoding: str = "utf-8",
    associated_data: bytes | None = None,
) -> str:
    encrypted = encrypt_bytes(plaintext.encode(encoding), material, associated_data=associated_data)
    return _urlsafe_b64_encode(encrypted)


def decrypt_string(
    encrypted_payload_b64: Annotated[
        UrlSafeBase64Text,
        doc("URL-safe base64 output created by encrypt_string"),
    ],
    material: AesGcmMaterial,
    *,
    encoding: str = "utf-8",
    associated_data: bytes | None = None,
) -> str:
    try:
        encrypted_payload = base64.urlsafe_b64decode(encrypted_payload_b64.encode("ascii"))
    except ValueError as error:
        msg = "Invalid encrypted payload: expected URL-safe base64 text"
        raise ValueError(msg) from error
    return decrypt_bytes(encrypted_payload, material, associated_data=associated_data).decode(encoding)


def encrypt_file(
    src: Annotated[Path, doc("Path to plaintext input file")],
    dst: Annotated[Path, doc("Path to encrypted output file")],
    material: AesGcmMaterial,
    *,
    associated_data: bytes | None = None,
) -> None:
    plaintext = src.read_bytes()
    dst.write_bytes(encrypt_bytes(plaintext, material, associated_data=associated_data))


def decrypt_file(
    src: Annotated[Path, doc("Path to encrypted input file")],
    dst: Annotated[Path, doc("Path to plaintext output file")],
    material: AesGcmMaterial,
    *,
    associated_data: bytes | None = None,
) -> None:
    encrypted_payload = src.read_bytes()
    dst.write_bytes(decrypt_bytes(encrypted_payload, material, associated_data=associated_data))

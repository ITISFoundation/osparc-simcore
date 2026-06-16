"""Streaming AES-256-GCM file/object encryption with a cross-language wire format.

This module implements a *streaming-only* authenticated-encryption protocol for
arbitrarily large files/objects. Plaintext is never fully materialised in memory:
encryption and decryption operate on file-like binary objects (``BinaryIO``) and
process the data in fixed-size chunks, so memory usage is bounded by ``chunk_size``.

The format is a clearly defined, versioned, language-neutral binary protocol intended
to interoperate with independent client implementations (e.g. a libsodium-based client).
No Python-specific serialization is used: every field is either a fixed-width
big-endian integer/byte block or an explicitly length-prefixed UTF-8 string.


Security properties
-------------------
* Confidentiality + integrity via AES-256-GCM (32-byte key, 12-byte nonce, 16-byte tag).
* A *per-file* key is derived with HKDF-SHA256 from a *job-level* key plus explicit
  context (``protocol_label``, ``job_id``, ``file_id``, ``file_role``). Distinct files /
  roles therefore use independent keys (domain separation).
* Each chunk uses a unique deterministic nonce derived from a random per-file seed and
  the chunk index, so a nonce is never reused with the same key.
* Each chunk's AAD binds the protocol magic/version, ``job_id``, ``file_id``,
  ``file_role``, the chunk index and a final-chunk marker. This prevents reordering,
  truncation, replay and cross-file substitution of chunks.
* The stream always contains at least one chunk and exactly one chunk flagged "final"
  (the last). Decryption fails if the final chunk is missing (truncation) or if extra
  data follows it.


Wire format (all integers big-endian / network byte order)
----------------------------------------------------------
Constants::

    protocol_label = b"simcore-aesgcm-stream-v1"   # HKDF + AAD domain separation
    magic          = b"SCAGSTRM"                    # 8 bytes, stream header marker
    version        = 1                              # uint16
    key size       = 32 bytes
    nonce size     = 12 bytes
    tag size       = 16 bytes
    default chunk  = 1024 * 1024 bytes (plaintext)

Length-prefixed string ``lp(s)`` (used identically in HKDF info and AAD)::

    lp(s) = uint16(len(utf8(s))) || utf8(s)        # s must encode to <= 65535 bytes

Per-file key derivation (HKDF-SHA256)::

    salt = None (empty)
    info = protocol_label || uint16(version)
           || lp(job_id) || lp(file_id) || lp(file_role)
    file_key = HKDF-SHA256(ikm=job_key, length=32, salt=None, info=info)

Stream header (28 bytes, struct format ">8sHHI12s")::

    offset 0  : magic            (8 bytes)  = b"SCAGSTRM"
    offset 8  : version          (uint16)   = 1
    offset 10 : flags            (uint16)   = 0 (reserved, must be 0)
    offset 12 : chunk_size       (uint32)   plaintext chunk size used by the writer
    offset 16 : base_nonce_seed  (12 bytes) random, generated per encryption

Per-chunk nonce (index ``i``, 0-based)::

    counter12 = b"\\x00\\x00\\x00\\x00" || uint64(i)     # 12 bytes
    nonce_i   = base_nonce_seed XOR counter12

Per-chunk AAD (index ``i``)::

    chunk_flags = uint8 (bit0 = 1 if this is the final chunk, else 0)
    aad_i = magic || uint16(version) || chunk_flags || uint64(i)
            || lp(job_id) || lp(file_id) || lp(file_role)

Per-chunk record on the wire (written sequentially after the header)::

    offset 0 : chunk_flags  (uint8)    bit0 = final-chunk marker
    offset 1 : ct_len       (uint32)   length of (ciphertext || tag) that follows
    offset 5 : ct_and_tag   (ct_len bytes)  AESGCM.encrypt() output = ciphertext || 16-byte tag

The plaintext length of a chunk is ``ct_len - tag size``. The final (possibly short or
empty) chunk is encoded the same way; the only difference is ``chunk_flags`` bit0 = 1.
An empty plaintext input produces exactly one final chunk whose plaintext length is 0
(``ct_len`` == tag size).
"""

from __future__ import annotations

import os
import struct
from pathlib import Path
from typing import Annotated, BinaryIO, Final

from annotated_types import doc
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

KEY_SIZE_BYTES: Final[int] = 32
NONCE_SIZE_BYTES: Final[int] = 12
TAG_SIZE_BYTES: Final[int] = 16
DEFAULT_CHUNK_SIZE_BYTES: Final[int] = 1024 * 1024

PROTOCOL_LABEL: Final[bytes] = b"simcore-aesgcm-stream-v1"
FORMAT_MAGIC: Final[bytes] = b"SCAGSTRM"
FORMAT_VERSION: Final[int] = 1

ALLOWED_FILE_ROLES: Final[frozenset[str]] = frozenset({"input", "output"})

_MAX_LP_STRING_BYTES: Final[int] = 0xFFFF
_FINAL_CHUNK_FLAG: Final[int] = 0b0000_0001

# Stream header: magic(8) | version(uint16) | flags(uint16) | chunk_size(uint32) | seed(12)
_HEADER_STRUCT: Final[struct.Struct] = struct.Struct(">8sHHI12s")
# Per-chunk record prefix: chunk_flags(uint8) | ct_len(uint32)
_CHUNK_PREFIX_STRUCT: Final[struct.Struct] = struct.Struct(">BI")
# uint16 / uint64 big-endian encoders reused for lp() and AAD/nonce construction
_U16_STRUCT: Final[struct.Struct] = struct.Struct(">H")
_U64_STRUCT: Final[struct.Struct] = struct.Struct(">Q")


class AesGcmStreamError(ValueError):
    """Base error for the streaming AES-GCM protocol."""


class AesGcmStreamFormatError(AesGcmStreamError):
    """Raised when the stream header or a chunk record is malformed or unsupported."""


class AesGcmStreamAuthError(AesGcmStreamError):
    """Raised when authentication fails (tampering, wrong key/context or truncation)."""


def generate_key() -> bytes:
    """Return a fresh random 32-byte job key suitable for AES-256-GCM derivation."""
    return os.urandom(KEY_SIZE_BYTES)


def _validate_key(job_key: bytes) -> None:
    if len(job_key) != KEY_SIZE_BYTES:
        msg = f"Invalid job key: expected {KEY_SIZE_BYTES} bytes, got {len(job_key)}"
        raise AesGcmStreamError(msg)


def _validate_file_role(file_role: str) -> None:
    if file_role not in ALLOWED_FILE_ROLES:
        allowed = ", ".join(sorted(ALLOWED_FILE_ROLES))
        msg = f"Invalid file_role {file_role!r}: must be one of {allowed}"
        raise AesGcmStreamError(msg)


def _validate_chunk_size(chunk_size: int) -> None:
    if chunk_size <= 0:
        msg = f"Invalid chunk_size: must be strictly positive, got {chunk_size}"
        raise AesGcmStreamError(msg)


def _length_prefixed(value: str) -> bytes:
    encoded = value.encode("utf-8")
    if len(encoded) > _MAX_LP_STRING_BYTES:
        msg = f"String field too long: {len(encoded)} bytes exceeds {_MAX_LP_STRING_BYTES} byte limit"
        raise AesGcmStreamError(msg)
    return _U16_STRUCT.pack(len(encoded)) + encoded


def _derive_file_key(
    job_key: bytes,
    *,
    job_id: str,
    file_id: str,
    file_role: str,
) -> bytes:
    info = (
        PROTOCOL_LABEL
        + _U16_STRUCT.pack(FORMAT_VERSION)
        + _length_prefixed(job_id)
        + _length_prefixed(file_id)
        + _length_prefixed(file_role)
    )
    hkdf = HKDF(algorithm=SHA256(), length=KEY_SIZE_BYTES, salt=None, info=info)
    return hkdf.derive(job_key)


def _chunk_nonce(base_nonce_seed: bytes, chunk_index: int) -> bytes:
    counter = b"\x00\x00\x00\x00" + _U64_STRUCT.pack(chunk_index)
    return bytes(a ^ b for a, b in zip(base_nonce_seed, counter, strict=True))


def _build_chunk_aad(
    *,
    chunk_index: int,
    is_final: bool,
    job_id: str,
    file_id: str,
    file_role: str,
) -> bytes:
    chunk_flags = _FINAL_CHUNK_FLAG if is_final else 0
    return (
        FORMAT_MAGIC
        + _U16_STRUCT.pack(FORMAT_VERSION)
        + bytes([chunk_flags])
        + _U64_STRUCT.pack(chunk_index)
        + _length_prefixed(job_id)
        + _length_prefixed(file_id)
        + _length_prefixed(file_role)
    )


def _read_exact(
    src: BinaryIO,
    size: Annotated[int, doc("Exact number of bytes to read")],
) -> bytes | None:
    """Read exactly ``size`` bytes; return ``None`` only at a clean stream boundary (0 bytes)."""
    buffer = bytearray()
    while len(buffer) < size:
        chunk = src.read(size - len(buffer))
        if not chunk:
            if not buffer:
                return None
            msg = "Truncated stream: unexpected end of input"
            raise AesGcmStreamFormatError(msg)
        buffer.extend(chunk)
    return bytes(buffer)


def _parse_header(
    src: BinaryIO,
) -> Annotated[bytes, doc("The 12-byte per-file base nonce seed from the header")]:
    header = _read_exact(src, _HEADER_STRUCT.size)
    if header is None:
        msg = "Truncated stream: missing header"
        raise AesGcmStreamFormatError(msg)

    magic, version, flags, _chunk_size, base_nonce_seed = _HEADER_STRUCT.unpack(header)
    if magic != FORMAT_MAGIC:
        msg = "Invalid stream header: bad magic"
        raise AesGcmStreamFormatError(msg)
    if version != FORMAT_VERSION:
        msg = f"Unsupported stream version: {version}"
        raise AesGcmStreamFormatError(msg)
    if flags != 0:
        msg = f"Unsupported stream flags: {flags}"
        raise AesGcmStreamFormatError(msg)
    return bytes(base_nonce_seed)


def encrypt_stream(
    src: BinaryIO,
    dst: BinaryIO,
    *,
    job_key: bytes,
    job_id: str,
    file_id: str,
    file_role: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE_BYTES,
) -> None:
    """Encrypt ``src`` into ``dst`` using the streaming AES-256-GCM protocol.

    Reads plaintext from ``src`` in ``chunk_size`` blocks and writes a versioned
    self-describing stream to ``dst``. Memory usage is bounded by ``chunk_size``.

    Raises:
        AesGcmStreamError: If ``job_key`` length, ``file_role`` or ``chunk_size`` are invalid.
    """
    _validate_key(job_key)
    _validate_file_role(file_role)
    _validate_chunk_size(chunk_size)

    file_key = _derive_file_key(job_key, job_id=job_id, file_id=file_id, file_role=file_role)
    aesgcm = AESGCM(file_key)
    base_nonce_seed = os.urandom(NONCE_SIZE_BYTES)

    dst.write(_HEADER_STRUCT.pack(FORMAT_MAGIC, FORMAT_VERSION, 0, chunk_size, base_nonce_seed))

    chunk_index = 0
    # One-chunk lookahead so the final chunk can be flagged unambiguously, including
    # the empty-input case (which still emits exactly one final chunk).
    pending = src.read(chunk_size)
    while True:
        next_chunk = src.read(chunk_size)
        is_final = not next_chunk
        nonce = _chunk_nonce(base_nonce_seed, chunk_index)
        aad = _build_chunk_aad(
            chunk_index=chunk_index,
            is_final=is_final,
            job_id=job_id,
            file_id=file_id,
            file_role=file_role,
        )
        ct_and_tag = aesgcm.encrypt(nonce, pending, aad)
        dst.write(_CHUNK_PREFIX_STRUCT.pack(_FINAL_CHUNK_FLAG if is_final else 0, len(ct_and_tag)))
        dst.write(ct_and_tag)

        if is_final:
            break
        pending = next_chunk
        chunk_index += 1


def decrypt_stream(
    src: BinaryIO,
    dst: BinaryIO,
    *,
    job_key: bytes,
    job_id: str,
    file_id: str,
    file_role: str,
) -> None:
    """Decrypt a stream produced by :func:`encrypt_stream` from ``src`` into ``dst``.

    Re-derives the per-file key, reconstructs per-chunk nonces and AAD, verifies every
    chunk's authentication tag and streams plaintext to ``dst``. Fails hard on any
    tampering, truncation, wrong key/context or unexpected trailing data.

    Raises:
        AesGcmStreamError: If ``job_key`` length or ``file_role`` are invalid.
        AesGcmStreamFormatError: If the header or a chunk record is malformed/unsupported.
        AesGcmStreamAuthError: If authentication fails or the stream is truncated.
    """
    _validate_key(job_key)
    _validate_file_role(file_role)

    base_nonce_seed = _parse_header(src)

    file_key = _derive_file_key(job_key, job_id=job_id, file_id=file_id, file_role=file_role)
    aesgcm = AESGCM(file_key)

    chunk_index = 0
    seen_final = False
    while not seen_final:
        prefix = _read_exact(src, _CHUNK_PREFIX_STRUCT.size)
        if prefix is None:
            msg = "Truncated stream: missing final chunk"
            raise AesGcmStreamAuthError(msg)

        chunk_flags, ct_len = _CHUNK_PREFIX_STRUCT.unpack(prefix)
        if ct_len < TAG_SIZE_BYTES:
            msg = "Invalid chunk record: ciphertext shorter than authentication tag"
            raise AesGcmStreamFormatError(msg)

        is_final = bool(chunk_flags & _FINAL_CHUNK_FLAG)
        ct_and_tag = _read_exact(src, ct_len)
        if ct_and_tag is None:
            msg = "Truncated stream: incomplete chunk ciphertext"
            raise AesGcmStreamFormatError(msg)

        nonce = _chunk_nonce(base_nonce_seed, chunk_index)
        aad = _build_chunk_aad(
            chunk_index=chunk_index,
            is_final=is_final,
            job_id=job_id,
            file_id=file_id,
            file_role=file_role,
        )
        try:
            plaintext = aesgcm.decrypt(nonce, ct_and_tag, aad)
        except InvalidTag as error:
            msg = "AES-GCM authentication failed"
            raise AesGcmStreamAuthError(msg) from error

        dst.write(plaintext)
        seen_final = is_final
        chunk_index += 1

    if src.read(1):
        msg = "Invalid stream: unexpected data after final chunk"
        raise AesGcmStreamFormatError(msg)


def encrypt_file(
    src: Annotated[Path, doc("Path to plaintext input file")],
    dst: Annotated[Path, doc("Path to encrypted output file")],
    *,
    job_key: bytes,
    job_id: str,
    file_id: str,
    file_role: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE_BYTES,
) -> None:
    """Thin ``Path`` wrapper around :func:`encrypt_stream` (opens files in binary mode)."""
    with src.open("rb") as src_stream, dst.open("wb") as dst_stream:
        encrypt_stream(
            src_stream,
            dst_stream,
            job_key=job_key,
            job_id=job_id,
            file_id=file_id,
            file_role=file_role,
            chunk_size=chunk_size,
        )


def decrypt_file(
    src: Annotated[Path, doc("Path to encrypted input file")],
    dst: Annotated[Path, doc("Path to plaintext output file")],
    *,
    job_key: bytes,
    job_id: str,
    file_id: str,
    file_role: str,
) -> None:
    """Thin ``Path`` wrapper around :func:`decrypt_stream` (opens files in binary mode)."""
    with src.open("rb") as src_stream, dst.open("wb") as dst_stream:
        decrypt_stream(
            src_stream,
            dst_stream,
            job_key=job_key,
            job_id=job_id,
            file_id=file_id,
            file_role=file_role,
        )

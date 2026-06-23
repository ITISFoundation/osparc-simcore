"""Streaming AES-256-GCM file/object encryption — normative cross-language protocol.

This module defines and implements ``simcore-aesgcm-stream-v1``, a streaming
authenticated-encryption protocol for arbitrarily large files/objects. Plaintext is
never fully materialised in memory: encryption and decryption operate on file-like
binary objects (``BinaryIO``) and process data in fixed-size chunks, so memory usage is
bounded by ``chunk_size``.

This docstring is the normative specification. Any independent implementation (e.g. a
libsodium-based client) that follows it byte-for-byte interoperates with this one.


Conventions
-----------
* All multi-byte integers are unsigned and big-endian (network byte order).
* All strings are encoded as UTF-8.
* Length-prefixed string (used identically wherever ``lp(s)`` appears below)::

      lp(s) = uint16(byte_length(utf8(s))) || utf8(s)     # utf8(s) must be <= 65535 bytes

* ``||`` denotes byte concatenation. ``XOR`` is bytewise exclusive-or of equal-length
  byte strings.


Constants
---------
::

    protocol_label = b"simcore-aesgcm-stream-v1"   # HKDF + AAD domain separation label
    magic          = b"SCAGSTRM"                    # 8 bytes, stream header marker
    version        = 1                              # uint16; this spec is version 1 only
    key size       = 32 bytes                       # AES-256
    nonce size     = 12 bytes                       # AES-GCM nonce
    tag size       = 16 bytes                       # AES-GCM authentication tag
    default chunk  = 1024 * 1024 bytes              # plaintext chunk size (writer default)


Cryptographic primitives
-------------------------
* AEAD: AES-256-GCM. ``AESGCM.encrypt(nonce, plaintext, aad)`` returns
  ``ciphertext || tag`` where ``tag`` is the trailing 16 bytes.
* KDF: HKDF-SHA256 with ``salt`` empty (none).


Per-file key derivation (HKDF-SHA256)
-------------------------------------
``file_role`` is mandatory and must be exactly ``"input"`` or ``"output"``
(case-sensitive). The per-file key is::

    info     = protocol_label || uint16(version)
               || lp(job_id) || lp(file_id) || lp(file_role)
    file_key = HKDF-SHA256(ikm=job_key, length=32, salt=<empty>, info=info)

Distinct ``(job_id, file_id, file_role)`` triples therefore yield independent keys
(domain separation).


Stream header (28 bytes, struct format ">8sHHI12s")
---------------------------------------------------
::

    offset 0  : magic            (8 bytes)  = b"SCAGSTRM"
    offset 8  : version          (uint16)   = 1
    offset 10 : flags            (uint16)   = 0   (reserved; must be 0)
    offset 12 : chunk_size       (uint32)   plaintext chunk size; must be > 0
    offset 16 : base_nonce_seed  (12 bytes) random, generated fresh per encryption


Per-chunk nonce (chunk index ``i``)
-----------------------------------
``i`` is zero-based and encoded as a uint64; it must be < 2**64::

    counter12 = b"\\x00\\x00\\x00\\x00" || uint64(i)     # 12 bytes
    nonce_i   = base_nonce_seed XOR counter12

Because ``base_nonce_seed`` is fresh per file and ``i`` is unique per chunk, a nonce is
never reused with the same key.


Per-chunk AAD (chunk index ``i``)
---------------------------------
::

    chunk_flags = uint8; bit0 = 1 if final chunk else 0; all other bits 0
    aad_i = magic || uint16(version) || chunk_flags || uint64(i)
            || lp(job_id) || lp(file_id) || lp(file_role)

The AAD binds magic/version, ``job_id``, ``file_id``, ``file_role``, the chunk index and
the final-chunk marker, preventing reordering, truncation, replay and cross-file
substitution of chunks.


Per-chunk record (written sequentially after the header)
--------------------------------------------------------
::

    offset 0 : chunk_flags  (uint8)    bit0 = final-chunk marker; other bits must be 0
    offset 1 : ct_len       (uint32)   byte length of (ciphertext || tag)
    offset 5 : ct_and_tag   (ct_len bytes) = AESGCM.encrypt(nonce_i, plaintext_i, aad_i)

The plaintext length of a chunk is ``ct_len - 16`` (tag size). Thus ``ct_len`` must be
>= 16. The final chunk is encoded identically except ``chunk_flags`` bit0 = 1. An empty
plaintext input still produces exactly one final chunk whose plaintext length is 0
(``ct_len`` == 16).


Protocol invariants (enforced on decryption)
---------------------------------------------
1. Header ``magic`` must equal ``b"SCAGSTRM"``.
2. Header ``version`` must equal 1.
3. Header ``flags`` must be 0.
4. Header ``chunk_size`` must be > 0.
5. ``file_role`` must be exactly ``"input"`` or ``"output"`` (case-sensitive).
6. ``job_key`` must be exactly 32 bytes.
7. For every chunk record, ``chunk_flags & ~bit0`` must be 0 (unknown bits rejected).
8. For every chunk record, ``ct_len`` must be >= 16.
9. Chunks are decrypted in order starting at index 0; each chunk's AAD/nonce uses its
   own index.
10. Exactly one chunk has the final marker set, and it is the last chunk read.
11. No bytes may follow the final chunk.
12. Any authentication-tag failure, truncation or violation of the above aborts
    decryption (no plaintext beyond the failing chunk is emitted as valid output).
"""

from __future__ import annotations

import os
import struct
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, BinaryIO, Final

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from dask_task_models_library.container_tasks.encryption import KEY_SIZE_BYTES
from pydantic import Field

NONCE_SIZE_BYTES: Final[int] = 12
TAG_SIZE_BYTES: Final[int] = 16
DEFAULT_CHUNK_SIZE_BYTES: Final[int] = 1024 * 1024

PROTOCOL_LABEL: Final[bytes] = b"simcore-aesgcm-stream-v1"
FORMAT_MAGIC: Final[bytes] = b"SCAGSTRM"
FORMAT_VERSION: Final[int] = 1

ALLOWED_FILE_ROLES: Final[frozenset[str]] = frozenset({"input", "output"})

_MAX_LP_STRING_BYTES: Final[int] = 0xFFFF
_FINAL_CHUNK_FLAG: Final[int] = 0b0000_0001
_KNOWN_CHUNK_FLAGS_MASK: Final[int] = _FINAL_CHUNK_FLAG
_MAX_CHUNK_INDEX_EXCLUSIVE: Final[int] = 2**64

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
    if not 0 <= chunk_index < _MAX_CHUNK_INDEX_EXCLUSIVE:
        msg = f"Invalid chunk index {chunk_index}: must be in [0, 2**64)"
        raise AesGcmStreamFormatError(msg)
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
    size: Annotated[int, Field(description="Exact number of bytes to read")],
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
) -> Annotated[
    tuple[int, bytes],
    Field(description="(plaintext chunk_size, 12-byte per-file base nonce seed) from the header"),
]:
    header = _read_exact(src, _HEADER_STRUCT.size)
    if header is None:
        msg = "Truncated stream: missing header"
        raise AesGcmStreamFormatError(msg)

    magic, version, flags, chunk_size, base_nonce_seed = _HEADER_STRUCT.unpack(header)
    if magic != FORMAT_MAGIC:
        msg = "Invalid stream header: bad magic"
        raise AesGcmStreamFormatError(msg)
    if version != FORMAT_VERSION:
        msg = f"Unsupported stream version: {version}"
        raise AesGcmStreamFormatError(msg)
    if flags != 0:
        msg = f"Unsupported stream flags: {flags}"
        raise AesGcmStreamFormatError(msg)
    if chunk_size <= 0:
        msg = f"Invalid stream header: chunk_size must be > 0, got {chunk_size}"
        raise AesGcmStreamFormatError(msg)
    return chunk_size, bytes(base_nonce_seed)


def encrypt_stream(
    src: BinaryIO,
    dst: BinaryIO,
    *,
    job_key: bytes,
    job_id: str,
    file_id: str,
    file_role: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE_BYTES,
    progress_cb: Annotated[
        Callable[[int], None] | None,
        Field(description="Called after each chunk with the cumulative plaintext bytes processed so far"),
    ] = None,
) -> None:
    """Encrypt ``src`` into ``dst`` using the streaming AES-256-GCM protocol.

    Reads plaintext from ``src`` in ``chunk_size`` blocks and writes a versioned
    self-describing stream to ``dst``. Memory usage is bounded by ``chunk_size``.

    This call is synchronous/blocking; offload it to a thread when used in async code.

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
    total_plaintext_bytes = 0
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

        total_plaintext_bytes += len(pending)
        if progress_cb is not None:
            progress_cb(total_plaintext_bytes)

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
    progress_cb: Annotated[
        Callable[[int], None] | None,
        Field(description="Called after each chunk with the cumulative plaintext bytes processed so far"),
    ] = None,
) -> None:
    """Decrypt a stream produced by :func:`encrypt_stream` from ``src`` into ``dst``.

    Re-derives the per-file key, reconstructs per-chunk nonces and AAD, verifies every
    chunk's authentication tag and streams plaintext to ``dst``. Fails hard on any
    tampering, truncation, wrong key/context or unexpected trailing data.

    This call is synchronous/blocking; offload it to a thread when used in async code.

    Raises:
        AesGcmStreamError: If ``job_key`` length or ``file_role`` are invalid.
        AesGcmStreamFormatError: If the header or a chunk record is malformed,
            unsupported or truncated.
        AesGcmStreamAuthError: If authentication fails or the final chunk is missing.
    """
    _validate_key(job_key)
    _validate_file_role(file_role)

    _chunk_size, base_nonce_seed = _parse_header(src)

    file_key = _derive_file_key(job_key, job_id=job_id, file_id=file_id, file_role=file_role)
    aesgcm = AESGCM(file_key)

    chunk_index = 0
    total_plaintext_bytes = 0
    seen_final = False
    while not seen_final:
        prefix = _read_exact(src, _CHUNK_PREFIX_STRUCT.size)
        if prefix is None:
            msg = "Truncated stream: missing final chunk"
            raise AesGcmStreamAuthError(msg)

        chunk_flags, ct_len = _CHUNK_PREFIX_STRUCT.unpack(prefix)
        if chunk_flags & ~_KNOWN_CHUNK_FLAGS_MASK:
            msg = f"Invalid chunk record: unknown flag bits set ({chunk_flags:#04x})"
            raise AesGcmStreamFormatError(msg)
        if ct_len < TAG_SIZE_BYTES:
            msg = "Invalid chunk record: ciphertext shorter than authentication tag"
            raise AesGcmStreamFormatError(msg)
        if ct_len > _chunk_size + TAG_SIZE_BYTES:
            msg = (
                "Invalid chunk record: ciphertext exceeds advertised chunk size "
                f"({ct_len} > {_chunk_size + TAG_SIZE_BYTES})"
            )
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
        total_plaintext_bytes += len(plaintext)
        if progress_cb is not None:
            progress_cb(total_plaintext_bytes)

        seen_final = is_final
        chunk_index += 1

    if src.read(1):
        msg = "Invalid stream: unexpected data after final chunk"
        raise AesGcmStreamFormatError(msg)


def encrypt_file(
    src: Annotated[Path, Field(description="Path to plaintext input file")],
    dst: Annotated[Path, Field(description="Path to encrypted output file")],
    *,
    job_key: bytes,
    job_id: str,
    file_id: str,
    file_role: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE_BYTES,
) -> None:
    """Utility function to encrypt a file following the streaming AES-GCM protocol, given and key/context.

    Arguments:
        job_key -- a 32-byte key used for encryption; must be the same as the one used for decryption
        job_id -- a string identifier for the job; must be the same as the one used for decryption
        file_id -- a string identifier for the file; must be the same as the one used for decryption
        file_role -- a string identifier for the file role; must be the same as the one used for decryption

    Keyword Arguments:
        src -- source file path
        dst -- destination file path
        chunk_size -- size of each encrypted chunk in bytes (default: {DEFAULT_CHUNK_SIZE_BYTES})

    Raises:
        AesGcmStreamError: If ``job_key`` length, ``file_role`` or ``chunk_size`` are invalid.
    """
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
    src: Annotated[Path, Field(description="Path to encrypted input file")],
    dst: Annotated[Path, Field(description="Path to plaintext output file")],
    *,
    job_key: bytes,
    job_id: str,
    file_id: str,
    file_role: str,
) -> None:
    """Utility function to decrypt a file following the streaming AES-GCM protocol,
    given the same key/context used for encryption.

    Arguments:
        job_key -- a 32-byte key used for decryption; must be the same as the one used for encryption
        job_id -- a string identifier for the job; must be the same as the one used for encryption
        file_id -- a string identifier for the file; must be the same as the one used for encryption
        file_role -- a string identifier for the file role; must be the same as the one used for encryption
                    and either "input" or "output"

    Keyword Arguments:
        src -- source file path
        dst -- destination file path

    Raises:
        AesGcmStreamError: If ``job_key`` length or ``file_role`` are invalid.
        AesGcmStreamFormatError: If the header or a chunk record is malformed/unsupported.
        AesGcmStreamAuthError: If authentication fails or the stream is truncated.
    """
    with src.open("rb") as src_stream, dst.open("wb") as dst_stream:
        decrypt_stream(
            src_stream,
            dst_stream,
            job_key=job_key,
            job_id=job_id,
            file_id=file_id,
            file_role=file_role,
        )

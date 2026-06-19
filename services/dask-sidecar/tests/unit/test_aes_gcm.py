# pylint: disable=redefined-outer-name
# pylint: disable=protected-access

import io
import os
import struct
from pathlib import Path

import pytest
from simcore_service_dask_sidecar import aes_gcm
from simcore_service_dask_sidecar.aes_gcm import (
    _CHUNK_PREFIX_STRUCT,
    _HEADER_STRUCT,
    _MAX_CHUNK_INDEX_EXCLUSIVE,
    _MAX_LP_STRING_BYTES,
    DEFAULT_CHUNK_SIZE_BYTES,
    FORMAT_MAGIC,
    FORMAT_VERSION,
    KEY_SIZE_BYTES,
    NONCE_SIZE_BYTES,
    PROTOCOL_LABEL,
    TAG_SIZE_BYTES,
    AesGcmStreamAuthError,
    AesGcmStreamError,
    AesGcmStreamFormatError,
    _build_chunk_aad,
    _chunk_nonce,
    _derive_file_key,
    _length_prefixed,
    decrypt_file,
    decrypt_stream,
    encrypt_file,
    encrypt_stream,
    generate_key,
)

_HEADER_SIZE = _HEADER_STRUCT.size
_CHUNK_PREFIX_SIZE = _CHUNK_PREFIX_STRUCT.size


@pytest.fixture
def job_key() -> bytes:
    return generate_key()


@pytest.fixture
def context() -> dict[str, str]:
    return {"job_id": "job-123", "file_id": "file-abc", "file_role": "input"}


def _encrypt_to_bytes(
    plaintext: bytes,
    job_key: bytes,
    context: dict[str, str],
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE_BYTES,
) -> bytes:
    dst = io.BytesIO()
    encrypt_stream(io.BytesIO(plaintext), dst, job_key=job_key, chunk_size=chunk_size, **context)
    return dst.getvalue()


def _decrypt_to_bytes(
    encrypted: bytes,
    job_key: bytes,
    context: dict[str, str],
) -> bytes:
    dst = io.BytesIO()
    decrypt_stream(io.BytesIO(encrypted), dst, job_key=job_key, **context)
    return dst.getvalue()


def _find_last_chunk_offset(encrypted: bytes) -> int:
    """Return the byte offset of the last chunk record's prefix."""
    offset = _HEADER_SIZE
    last_offset = offset
    while offset < len(encrypted):
        last_offset = offset
        _flags, ct_len = _CHUNK_PREFIX_STRUCT.unpack(encrypted[offset : offset + _CHUNK_PREFIX_SIZE])
        offset += _CHUNK_PREFIX_SIZE + ct_len
    return last_offset


def test_generate_key_size():
    assert len(generate_key()) == KEY_SIZE_BYTES


def test_roundtrip_small_content(job_key: bytes, context: dict[str, str]):
    plaintext = b"hello\x00world"
    encrypted = _encrypt_to_bytes(plaintext, job_key, context)
    assert encrypted != plaintext
    assert _decrypt_to_bytes(encrypted, job_key, context) == plaintext


def test_roundtrip_empty_content(job_key: bytes, context: dict[str, str]):
    encrypted = _encrypt_to_bytes(b"", job_key, context)
    # an empty input still produces a header + exactly one final chunk
    assert len(encrypted) == _HEADER_SIZE + _CHUNK_PREFIX_SIZE + TAG_SIZE_BYTES
    assert _decrypt_to_bytes(encrypted, job_key, context) == b""


def test_roundtrip_multichunk_large_content(job_key: bytes, context: dict[str, str]):
    chunk_size = 64
    plaintext = os.urandom(chunk_size * 10)  # exactly 10 full chunks
    encrypted = _encrypt_to_bytes(plaintext, job_key, context, chunk_size=chunk_size)
    assert _decrypt_to_bytes(encrypted, job_key, context) == plaintext


def test_roundtrip_final_partial_chunk(job_key: bytes, context: dict[str, str]):
    chunk_size = 100
    # not a multiple of the chunk size: last chunk is a short partial chunk
    plaintext = os.urandom(chunk_size * 3 + 17)
    encrypted = _encrypt_to_bytes(plaintext, job_key, context, chunk_size=chunk_size)
    assert _decrypt_to_bytes(encrypted, job_key, context) == plaintext


def test_roundtrip_single_chunk_exact_size(job_key: bytes, context: dict[str, str]):
    chunk_size = 128
    plaintext = os.urandom(chunk_size)  # exactly one final chunk, no trailing empty chunk
    encrypted = _encrypt_to_bytes(plaintext, job_key, context, chunk_size=chunk_size)
    assert _decrypt_to_bytes(encrypted, job_key, context) == plaintext


def test_encrypt_stream_reports_cumulative_progress(job_key: bytes, context: dict[str, str]):
    chunk_size = 64
    plaintext = os.urandom(chunk_size * 3 + 7)  # 3 full chunks + a short final chunk
    progress: list[int] = []
    encrypt_stream(
        io.BytesIO(plaintext),
        io.BytesIO(),
        job_key=job_key,
        chunk_size=chunk_size,
        progress_cb=progress.append,
        **context,
    )
    # one callback per chunk record (3 full + 1 final), strictly increasing, ending at total
    assert progress == [chunk_size, chunk_size * 2, chunk_size * 3, len(plaintext)]


def test_decrypt_stream_reports_cumulative_progress(job_key: bytes, context: dict[str, str]):
    chunk_size = 64
    plaintext = os.urandom(chunk_size * 3 + 7)
    encrypted = _encrypt_to_bytes(plaintext, job_key, context, chunk_size=chunk_size)
    progress: list[int] = []
    decrypt_stream(
        io.BytesIO(encrypted),
        io.BytesIO(),
        job_key=job_key,
        progress_cb=progress.append,
        **context,
    )
    assert progress == [chunk_size, chunk_size * 2, chunk_size * 3, len(plaintext)]


def test_encrypt_stream_progress_on_empty_input(job_key: bytes, context: dict[str, str]):
    progress: list[int] = []
    encrypt_stream(
        io.BytesIO(b""),
        io.BytesIO(),
        job_key=job_key,
        progress_cb=progress.append,
        **context,
    )
    # empty input still emits exactly one final chunk, reporting 0 plaintext bytes
    assert progress == [0]


def test_streams_without_progress_cb_do_not_fail(job_key: bytes, context: dict[str, str]):
    plaintext = os.urandom(200)
    encrypted = _encrypt_to_bytes(plaintext, job_key, context)
    assert _decrypt_to_bytes(encrypted, job_key, context) == plaintext


def test_two_encryptions_differ_due_to_random_seed(job_key: bytes, context: dict[str, str]):
    plaintext = b"same plaintext"
    one = _encrypt_to_bytes(plaintext, job_key, context)
    two = _encrypt_to_bytes(plaintext, job_key, context)
    assert one != two
    assert _decrypt_to_bytes(one, job_key, context) == plaintext
    assert _decrypt_to_bytes(two, job_key, context) == plaintext


def test_header_has_expected_shape(job_key: bytes, context: dict[str, str]):
    encrypted = _encrypt_to_bytes(b"abc", job_key, context)
    magic, version, flags, chunk_size, seed = _HEADER_STRUCT.unpack(encrypted[:_HEADER_SIZE])
    assert magic == FORMAT_MAGIC
    assert version == FORMAT_VERSION
    assert flags == 0
    assert chunk_size == DEFAULT_CHUNK_SIZE_BYTES
    assert len(seed) == NONCE_SIZE_BYTES


def test_decrypt_rejects_tampered_magic(job_key: bytes, context: dict[str, str]):
    encrypted = bytearray(_encrypt_to_bytes(b"abc", job_key, context))
    encrypted[0] ^= 0xFF
    with pytest.raises(AesGcmStreamFormatError, match="bad magic"):
        _decrypt_to_bytes(bytes(encrypted), job_key, context)


def test_decrypt_rejects_unsupported_version(job_key: bytes, context: dict[str, str]):
    encrypted = bytearray(_encrypt_to_bytes(b"abc", job_key, context))
    # version is the uint16 right after the 8-byte magic
    encrypted[len(FORMAT_MAGIC) : len(FORMAT_MAGIC) + 2] = struct.pack(">H", FORMAT_VERSION + 1)
    with pytest.raises(AesGcmStreamFormatError, match="Unsupported stream version"):
        _decrypt_to_bytes(bytes(encrypted), job_key, context)


def test_decrypt_rejects_tampered_base_nonce_seed(job_key: bytes, context: dict[str, str]):
    encrypted = bytearray(_encrypt_to_bytes(b"abc", job_key, context))
    encrypted[_HEADER_SIZE - 1] ^= 0x01  # last byte of the seed
    with pytest.raises(AesGcmStreamAuthError, match="authentication failed"):
        _decrypt_to_bytes(bytes(encrypted), job_key, context)


def test_decrypt_rejects_tampered_ciphertext(job_key: bytes, context: dict[str, str]):
    encrypted = bytearray(_encrypt_to_bytes(b"abc", job_key, context))
    # flip a byte inside the ciphertext (right after header + chunk prefix)
    encrypted[_HEADER_SIZE + _CHUNK_PREFIX_SIZE] ^= 0x01
    with pytest.raises(AesGcmStreamAuthError, match="authentication failed"):
        _decrypt_to_bytes(bytes(encrypted), job_key, context)


def test_decrypt_rejects_chunk_larger_than_advertised_size(job_key: bytes, context: dict[str, str]):
    chunk_size = 32
    encrypted = bytearray(_encrypt_to_bytes(os.urandom(chunk_size), job_key, context, chunk_size=chunk_size))
    encrypted[_HEADER_SIZE : _HEADER_SIZE + _CHUNK_PREFIX_SIZE] = _CHUNK_PREFIX_STRUCT.pack(
        0,
        chunk_size + TAG_SIZE_BYTES + 1,
    )

    with pytest.raises(AesGcmStreamFormatError, match="ciphertext exceeds advertised chunk size"):
        _decrypt_to_bytes(bytes(encrypted), job_key, context)


def test_decrypt_rejects_tampered_tag(job_key: bytes, context: dict[str, str]):
    encrypted = bytearray(_encrypt_to_bytes(b"abc", job_key, context))
    encrypted[-1] ^= 0x01  # last byte is part of the GCM tag
    with pytest.raises(AesGcmStreamAuthError, match="authentication failed"):
        _decrypt_to_bytes(bytes(encrypted), job_key, context)


def test_decrypt_rejects_wrong_job_id(job_key: bytes, context: dict[str, str]):
    encrypted = _encrypt_to_bytes(b"abc", job_key, context)
    with pytest.raises(AesGcmStreamAuthError, match="authentication failed"):
        _decrypt_to_bytes(encrypted, job_key, {**context, "job_id": "other-job"})


def test_decrypt_rejects_wrong_file_id(job_key: bytes, context: dict[str, str]):
    encrypted = _encrypt_to_bytes(b"abc", job_key, context)
    with pytest.raises(AesGcmStreamAuthError, match="authentication failed"):
        _decrypt_to_bytes(encrypted, job_key, {**context, "file_id": "other-file"})


def test_decrypt_rejects_wrong_file_role(job_key: bytes, context: dict[str, str]):
    encrypted = _encrypt_to_bytes(b"abc", job_key, context)
    with pytest.raises(AesGcmStreamAuthError, match="authentication failed"):
        _decrypt_to_bytes(encrypted, job_key, {**context, "file_role": "output"})


def test_decrypt_rejects_wrong_job_key(job_key: bytes, context: dict[str, str]):
    encrypted = _encrypt_to_bytes(b"abc", job_key, context)
    with pytest.raises(AesGcmStreamAuthError, match="authentication failed"):
        _decrypt_to_bytes(encrypted, generate_key(), context)


def test_encrypt_rejects_unsupported_file_role(job_key: bytes, context: dict[str, str]):
    with pytest.raises(AesGcmStreamError, match="Invalid file_role"):
        _encrypt_to_bytes(b"abc", job_key, {**context, "file_role": "sidecar"})


def test_decrypt_rejects_unsupported_file_role(job_key: bytes, context: dict[str, str]):
    encrypted = _encrypt_to_bytes(b"abc", job_key, context)
    with pytest.raises(AesGcmStreamError, match="Invalid file_role"):
        _decrypt_to_bytes(encrypted, job_key, {**context, "file_role": "sidecar"})


@pytest.mark.parametrize("bad_key", [b"", os.urandom(16), os.urandom(31), os.urandom(33)])
def test_encrypt_rejects_invalid_key_length(bad_key: bytes, context: dict[str, str]):
    with pytest.raises(AesGcmStreamError, match="Invalid job key"):
        _encrypt_to_bytes(b"abc", bad_key, context)


def test_encrypt_rejects_non_positive_chunk_size(job_key: bytes, context: dict[str, str]):
    with pytest.raises(AesGcmStreamError, match="Invalid chunk_size"):
        _encrypt_to_bytes(b"abc", job_key, context, chunk_size=0)


def test_decrypt_rejects_truncated_stream_missing_final_chunk(job_key: bytes, context: dict[str, str]):
    chunk_size = 32
    plaintext = os.urandom(chunk_size * 3)
    encrypted = bytearray(_encrypt_to_bytes(plaintext, job_key, context, chunk_size=chunk_size))
    # drop the last chunk record entirely so no final-flagged chunk is ever reached
    last_prefix_offset = _find_last_chunk_offset(bytes(encrypted))
    truncated = bytes(encrypted[:last_prefix_offset])
    with pytest.raises(AesGcmStreamAuthError, match="missing final chunk"):
        _decrypt_to_bytes(truncated, job_key, context)


def test_decrypt_rejects_trailing_data_after_final_chunk(job_key: bytes, context: dict[str, str]):
    encrypted = _encrypt_to_bytes(b"abc", job_key, context) + b"garbage"
    with pytest.raises(AesGcmStreamFormatError, match="unexpected data after final"):
        _decrypt_to_bytes(encrypted, job_key, context)


def test_decrypt_rejects_missing_header(job_key: bytes, context: dict[str, str]):
    with pytest.raises(AesGcmStreamFormatError, match="missing header"):
        _decrypt_to_bytes(b"", job_key, context)


def test_decrypt_rejects_partial_header(job_key: bytes, context: dict[str, str]):
    with pytest.raises(AesGcmStreamFormatError, match="unexpected end of input"):
        _decrypt_to_bytes(b"short", job_key, context)


def test_decrypt_rejects_zero_chunk_size_in_header(job_key: bytes, context: dict[str, str]):
    encrypted = bytearray(_encrypt_to_bytes(b"abc", job_key, context))
    # header layout: magic(8) | version(uint16) | flags(uint16) | chunk_size(uint32) | seed(12)
    chunk_size_offset = len(FORMAT_MAGIC) + 2 + 2
    encrypted[chunk_size_offset : chunk_size_offset + 4] = struct.pack(">I", 0)
    with pytest.raises(AesGcmStreamFormatError, match="chunk_size must be > 0"):
        _decrypt_to_bytes(bytes(encrypted), job_key, context)


def test_decrypt_rejects_unknown_chunk_flag_bits(job_key: bytes, context: dict[str, str]):
    encrypted = bytearray(_encrypt_to_bytes(b"abc", job_key, context))
    # first chunk record's flags byte sits right after the header; set an unknown bit
    encrypted[_HEADER_SIZE] |= 0b0000_0010
    with pytest.raises(AesGcmStreamFormatError, match="unknown flag bits"):
        _decrypt_to_bytes(bytes(encrypted), job_key, context)


def test_decrypt_rejects_unsupported_header_flags(job_key: bytes, context: dict[str, str]):
    encrypted = bytearray(_encrypt_to_bytes(b"abc", job_key, context))
    # header layout: magic(8) | version(uint16) | flags(uint16) | chunk_size(uint32) | seed(12)
    flags_offset = len(FORMAT_MAGIC) + 2
    encrypted[flags_offset : flags_offset + 2] = struct.pack(">H", 1)
    with pytest.raises(AesGcmStreamFormatError, match="Unsupported stream flags"):
        _decrypt_to_bytes(bytes(encrypted), job_key, context)


def test_decrypt_rejects_chunk_ct_len_shorter_than_tag(job_key: bytes, context: dict[str, str]):
    encrypted = bytearray(_encrypt_to_bytes(b"abc", job_key, context))
    # chunk prefix sits right after the header: chunk_flags(uint8) | ct_len(uint32)
    ct_len_offset = _HEADER_SIZE + 1
    encrypted[ct_len_offset : ct_len_offset + 4] = struct.pack(">I", TAG_SIZE_BYTES - 1)
    with pytest.raises(AesGcmStreamFormatError, match="shorter than authentication tag"):
        _decrypt_to_bytes(bytes(encrypted), job_key, context)


def test_decrypt_rejects_incomplete_chunk_ciphertext(job_key: bytes, context: dict[str, str]):
    encrypted = bytearray(_encrypt_to_bytes(b"abc", job_key, context))
    # keep the valid chunk prefix but drop all of its declared ciphertext bytes
    truncated = bytes(encrypted[: _HEADER_SIZE + _CHUNK_PREFIX_SIZE])
    with pytest.raises(AesGcmStreamFormatError, match="incomplete chunk ciphertext"):
        _decrypt_to_bytes(truncated, job_key, context)


def test_length_prefixed_rejects_oversized_string():
    too_long = "x" * (_MAX_LP_STRING_BYTES + 1)
    with pytest.raises(AesGcmStreamError, match="String field too long"):
        _length_prefixed(too_long)


def test_chunk_nonce_rejects_out_of_range_index():
    seed = os.urandom(NONCE_SIZE_BYTES)
    with pytest.raises(AesGcmStreamFormatError, match="Invalid chunk index"):
        _chunk_nonce(seed, _MAX_CHUNK_INDEX_EXCLUSIVE)


class _ReadSizeRecorder(io.BytesIO):
    """BytesIO that records the size argument of every read() call."""

    def __init__(self, data: bytes) -> None:
        super().__init__(data)
        self.read_sizes: list[int | None] = []

    def read(self, size: int | None = -1, /) -> bytes:
        self.read_sizes.append(size)
        return super().read(size)


def test_encrypt_reads_are_bounded_by_chunk_size(job_key: bytes, context: dict[str, str]):
    chunk_size = 64
    plaintext = os.urandom(chunk_size * 5 + 3)
    recorder = _ReadSizeRecorder(plaintext)
    encrypt_stream(recorder, io.BytesIO(), job_key=job_key, chunk_size=chunk_size, **context)
    # every explicit read is bounded by chunk_size: the whole file is never read at once
    assert recorder.read_sizes
    assert all(size == chunk_size for size in recorder.read_sizes)
    assert max(recorder.read_sizes) < len(plaintext)


def test_decrypt_reads_are_bounded(job_key: bytes, context: dict[str, str]):
    chunk_size = 64
    plaintext = os.urandom(chunk_size * 5 + 3)
    encrypted = _encrypt_to_bytes(plaintext, job_key, context, chunk_size=chunk_size)
    recorder = _ReadSizeRecorder(encrypted)
    decrypt_stream(recorder, io.BytesIO(), job_key=job_key, **context)
    # decryption only ever requests header/prefix/ciphertext-sized reads, never the
    # full ciphertext at once
    assert all(size is None or size <= chunk_size + TAG_SIZE_BYTES for size in recorder.read_sizes)


def test_module_does_not_use_whole_file_read_write_apis():
    source = Path(aes_gcm.__file__).read_text(encoding="utf-8")
    assert "read_bytes" not in source
    assert "write_bytes" not in source


def test_nonce_derivation_matches_specification():
    seed = bytes(range(NONCE_SIZE_BYTES))
    # nonce_i = seed XOR (4 zero bytes || uint64_be(i))
    expected_index_5 = bytes(a ^ b for a, b in zip(seed, b"\x00\x00\x00\x00" + struct.pack(">Q", 5), strict=True))
    assert _chunk_nonce(seed, 5) == expected_index_5
    # index 0 leaves the seed unchanged
    assert _chunk_nonce(seed, 0) == seed


def test_chunk_aad_matches_specification():
    def lp(value: str) -> bytes:
        encoded = value.encode("utf-8")
        return struct.pack(">H", len(encoded)) + encoded

    aad = _build_chunk_aad(
        chunk_index=7,
        is_final=True,
        job_id="job-123",
        file_id="file-abc",
        file_role="input",
    )
    expected = (
        FORMAT_MAGIC
        + struct.pack(">H", FORMAT_VERSION)
        + bytes([0b0000_0001])
        + struct.pack(">Q", 7)
        + lp("job-123")
        + lp("file-abc")
        + lp("input")
    )
    assert aad == expected


def test_hkdf_derivation_is_deterministic_and_domain_separated():
    base_key = b"\x00" * KEY_SIZE_BYTES
    key_a = _derive_file_key(base_key, job_id="job-123", file_id="file-abc", file_role="input")
    key_b = _derive_file_key(base_key, job_id="job-123", file_id="file-abc", file_role="input")
    # deterministic for identical context
    assert key_a == key_b
    assert len(key_a) == KEY_SIZE_BYTES
    # different role -> different key (domain separation)
    key_other_role = _derive_file_key(base_key, job_id="job-123", file_id="file-abc", file_role="output")
    assert key_other_role != key_a
    # different file -> different key
    key_other_file = _derive_file_key(base_key, job_id="job-123", file_id="file-xyz", file_role="input")
    assert key_other_file != key_a
    # the documented HKDF info layout starts with the protocol label
    assert PROTOCOL_LABEL == b"simcore-aesgcm-stream-v1"


def test_path_wrappers_roundtrip(job_key: bytes, context: dict[str, str], tmp_path: Path):
    src = tmp_path / "plain.bin"
    encrypted = tmp_path / "encrypted.bin"
    decrypted = tmp_path / "decrypted.bin"

    payload = os.urandom(200_000)
    src.write_bytes(payload)
    encrypt_file(src, encrypted, job_key=job_key, chunk_size=4096, **context)
    decrypt_file(encrypted, decrypted, job_key=job_key, **context)

    assert decrypted.read_bytes() == payload


def test_path_wrappers_reject_wrong_context(job_key: bytes, context: dict[str, str], tmp_path: Path):
    src = tmp_path / "plain.bin"
    encrypted = tmp_path / "encrypted.bin"
    decrypted = tmp_path / "decrypted.bin"

    src.write_bytes(b"file-data")
    encrypt_file(src, encrypted, job_key=job_key, **context)

    with pytest.raises(AesGcmStreamAuthError, match="authentication failed"):
        decrypt_file(encrypted, decrypted, job_key=job_key, **{**context, "file_role": "output"})

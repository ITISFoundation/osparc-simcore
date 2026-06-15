# pylint: disable=redefined-outer-name

import base64

import pytest
from simcore_service_dask_sidecar.aes_gcm import (
    _ENVELOPE_HEADER_STRUCT,
    FORMAT_MAGIC,
    FORMAT_VERSION,
    KEY_SIZE_BYTES,
    NONCE_SIZE_BYTES,
    AesGcmMaterial,
    decrypt_bytes,
    decrypt_file,
    decrypt_string,
    encrypt_bytes,
    encrypt_file,
    encrypt_string,
    generate_base_nonce,
    generate_base_nonce_b64,
    generate_key,
    generate_key_b64,
)


@pytest.fixture
def material():
    return AesGcmMaterial.create()


def test_generate_key_and_nonce_sizes():
    assert len(generate_key()) == KEY_SIZE_BYTES
    assert len(generate_base_nonce()) == NONCE_SIZE_BYTES


def test_generate_key_and_nonce_b64_sizes():
    key = base64.urlsafe_b64decode(generate_key_b64().encode("ascii"))
    base_nonce = base64.urlsafe_b64decode(generate_base_nonce_b64().encode("ascii"))
    assert len(key) == KEY_SIZE_BYTES
    assert len(base_nonce) == NONCE_SIZE_BYTES


def test_material_base64_roundtrip(material):
    reloaded = AesGcmMaterial.from_base64(material.key_b64(), material.base_nonce_b64())
    assert reloaded == material


def test_material_from_base64_rejects_invalid_key_length(material):
    invalid_key = base64.urlsafe_b64encode(material.key[:-1]).decode("ascii")
    with pytest.raises(ValueError, match="Invalid AES-GCM key"):
        AesGcmMaterial.from_base64(invalid_key, material.base_nonce_b64())


def test_material_from_base64_rejects_invalid_nonce_length(material):
    invalid_nonce = base64.urlsafe_b64encode(material.base_nonce[:-1]).decode("ascii")
    with pytest.raises(ValueError, match="Invalid AES-GCM base nonce"):
        AesGcmMaterial.from_base64(material.key_b64(), invalid_nonce)


def test_material_from_base64_rejects_non_ascii_values(material):
    with pytest.raises(ValueError, match="expected URL-safe base64 text"):
        AesGcmMaterial.from_base64("你好", material.base_nonce_b64())


def test_encrypt_decrypt_bytes_roundtrip(material):
    plaintext = b"hello\x00world"
    encrypted = encrypt_bytes(plaintext, material)
    assert encrypted != plaintext
    assert decrypt_bytes(encrypted, material) == plaintext


def test_encrypt_bytes_uses_randomized_salt(material):
    plaintext = b"same plaintext"
    encrypted_one = encrypt_bytes(plaintext, material)
    encrypted_two = encrypt_bytes(plaintext, material)
    assert encrypted_one != encrypted_two
    assert decrypt_bytes(encrypted_one, material) == plaintext
    assert decrypt_bytes(encrypted_two, material) == plaintext


def test_decrypt_bytes_rejects_too_short_payload(material):
    with pytest.raises(ValueError, match="too short"):
        decrypt_bytes(b"short", material)


def test_decrypt_bytes_rejects_invalid_magic(material):
    encrypted = encrypt_bytes(b"abc", material)
    tampered = b"WRONG" + encrypted[5:]
    with pytest.raises(ValueError, match="Invalid AES-GCM payload header"):
        decrypt_bytes(tampered, material)


def test_decrypt_bytes_rejects_unsupported_version(material):
    encrypted = bytearray(encrypt_bytes(b"abc", material))
    encrypted[len(FORMAT_MAGIC)] = FORMAT_VERSION + 1
    with pytest.raises(ValueError, match="Unsupported AES-GCM payload version"):
        decrypt_bytes(bytes(encrypted), material)


def test_decrypt_bytes_rejects_modified_ciphertext(material):
    encrypted = bytearray(encrypt_bytes(b"abc", material))
    encrypted[-1] ^= 0x01
    with pytest.raises(ValueError, match="authentication failed"):
        decrypt_bytes(bytes(encrypted), material)


def test_decrypt_bytes_rejects_wrong_material(material):
    encrypted = encrypt_bytes(b"abc", material)
    wrong_material = AesGcmMaterial.create()
    with pytest.raises(ValueError, match="authentication failed"):
        decrypt_bytes(encrypted, wrong_material)


def test_encrypt_and_decrypt_string_roundtrip(material):
    plaintext = "hello with unicode: € and ä"
    encrypted_b64 = encrypt_string(plaintext, material)
    assert encrypted_b64 != plaintext
    assert decrypt_string(encrypted_b64, material) == plaintext


def test_decrypt_string_rejects_non_ascii_payload(material):
    with pytest.raises(ValueError, match="expected URL-safe base64 text"):
        decrypt_string("你好", material)


def test_encrypt_and_decrypt_file_roundtrip(material, tmp_path):
    src = tmp_path / "plain.bin"
    encrypted = tmp_path / "encrypted.bin"
    decrypted = tmp_path / "decrypted.bin"

    src.write_bytes(b"file-bytes\x00\x01\x02")
    encrypt_file(src, encrypted, material)
    decrypt_file(encrypted, decrypted, material)

    assert decrypted.read_bytes() == src.read_bytes()


def test_file_decryption_respects_associated_data(material, tmp_path):
    src = tmp_path / "plain.bin"
    encrypted = tmp_path / "encrypted.bin"
    decrypted = tmp_path / "decrypted.bin"

    src.write_bytes(b"file-data")
    encrypt_file(src, encrypted, material, associated_data=b"context")

    with pytest.raises(ValueError, match="authentication failed"):
        decrypt_file(encrypted, decrypted, material, associated_data=b"wrong-context")


def test_envelope_has_expected_header_shape(material):
    payload = encrypt_bytes(b"abc", material)
    header = payload[: _ENVELOPE_HEADER_STRUCT.size]
    magic, version, salt = _ENVELOPE_HEADER_STRUCT.unpack(header)
    assert magic == FORMAT_MAGIC
    assert version == FORMAT_VERSION
    assert len(salt) == NONCE_SIZE_BYTES

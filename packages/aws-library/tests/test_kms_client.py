# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=protected-access


from collections.abc import AsyncIterator

import pytest
from aws_library.kms import (
    KMSInvalidCiphertextError,
    KMSKeyNotFoundError,
    KMSNotConnectedError,
    SimcoreKMSAPI,
)
from faker import Faker
from moto.server import ThreadedMotoServer
from settings_library.kms import KMSSettings


@pytest.fixture
async def simcore_kms_api(
    mocked_kms_server_settings: KMSSettings,
) -> AsyncIterator[SimcoreKMSAPI]:
    kms = await SimcoreKMSAPI.create(settings=mocked_kms_server_settings)
    assert kms
    yield kms
    await kms.close()


async def test_kms_client_lifespan(simcore_kms_api: SimcoreKMSAPI): ...


async def test_ping(
    mocked_aws_server: ThreadedMotoServer,
    simcore_kms_api: SimcoreKMSAPI,
    faker: Faker,
):
    assert await simcore_kms_api.ping() is True
    mocked_aws_server.stop()
    assert await simcore_kms_api.ping() is False
    with pytest.raises(KMSNotConnectedError):
        await simcore_kms_api.encrypt(faker.binary(length=32))
    mocked_aws_server.start()
    assert await simcore_kms_api.ping() is True


async def test_encrypt_decrypt_roundtrip(
    mocked_aws_server: ThreadedMotoServer,
    simcore_kms_api: SimcoreKMSAPI,
    faker: Faker,
):
    plaintext = faker.binary(length=32)

    ciphertext = await simcore_kms_api.encrypt(plaintext)
    assert ciphertext != plaintext

    decrypted = await simcore_kms_api.decrypt(ciphertext)
    assert decrypted == plaintext


async def test_encrypt_decrypt_with_encryption_context(
    mocked_aws_server: ThreadedMotoServer,
    simcore_kms_api: SimcoreKMSAPI,
    faker: Faker,
):
    plaintext = faker.binary(length=32)
    encryption_context = {"project_id": faker.uuid4()}

    ciphertext = await simcore_kms_api.encrypt(plaintext, encryption_context=encryption_context)

    decrypted = await simcore_kms_api.decrypt(ciphertext, encryption_context=encryption_context)
    assert decrypted == plaintext

    # decrypting without the matching encryption context must fail
    with pytest.raises(KMSInvalidCiphertextError):
        await simcore_kms_api.decrypt(ciphertext)
    with pytest.raises(KMSInvalidCiphertextError):
        await simcore_kms_api.decrypt(ciphertext, encryption_context={"project_id": faker.uuid4()})


async def test_decrypt_invalid_ciphertext_raises(
    mocked_aws_server: ThreadedMotoServer,
    simcore_kms_api: SimcoreKMSAPI,
    faker: Faker,
):
    with pytest.raises(KMSInvalidCiphertextError):
        await simcore_kms_api.decrypt(faker.binary(length=32))


async def test_encrypt_with_unknown_key_id_raises(
    mocked_aws_server: ThreadedMotoServer,
    simcore_kms_api: SimcoreKMSAPI,
    faker: Faker,
):
    unknown_key_id = faker.uuid4()
    with pytest.raises(KMSKeyNotFoundError):
        await simcore_kms_api.encrypt(faker.binary(length=32), key_id=unknown_key_id)

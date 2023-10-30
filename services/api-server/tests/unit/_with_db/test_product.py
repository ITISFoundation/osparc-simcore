import httpx
from simcore_service_api_server.models.domain.api_keys import ApiKeyInDB


async def test_product_associated_from_user(
    client: httpx.AsyncClient, two_fake_api_keys: list[ApiKeyInDB]
) -> None:
    assert client
    assert len(two_fake_api_keys) == 2
    key1, key2 = two_fake_api_keys
    assert key1.product_name != key2.product_name
    print(key1)
    print(key2)

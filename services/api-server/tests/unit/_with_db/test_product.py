import httpx


async def test_product_associated_from_user(
    client: httpx.AsyncClient, fake_api_keys
) -> None:
    assert client
    fake_key_generator = fake_api_keys(2)
    async for key in fake_key_generator:
        print(key.product_name)

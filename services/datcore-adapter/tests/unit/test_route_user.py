# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


import httpx2
from starlette import status


async def test_users_profile_entrypoint(
    async_client: httpx2.AsyncClient,
    pennsieve_subsystem_mock,
    pennsieve_api_headers: dict[str, str],
):
    response = await async_client.get(
        "v0/user/profile",
        headers=pennsieve_api_headers,
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data

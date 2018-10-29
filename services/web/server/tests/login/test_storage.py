# pylint:disable=unused-import
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import pytest
from aiohttp import web

from utils_login import LoggedUser
from utils_assert import assert_status
from servicelib.response_utils import unwrap_envelope

# from simcore_service_webserver.application_keys import APP_CONFIG_KEY
# from simcore_service_webserver.storage import setup_storage
# from simcore_service_webserver.rest import setup_rest


@pytest.mark.travis
async def test_storage_locations(client):
    url = "/v0/storage/locations"

    resp = await client.get(url)
    await assert_status(resp, web.HTTPUnauthorized)

    async with LoggedUser(client) as user:
        print("Logged user:", user) # TODO: can use in the test

        resp = await client.get(url)

        payload = await resp.json()
        assert resp.status == 200, str(payload)

        data, error = unwrap_envelope(payload)

        assert len(data) == 1
        assert not error

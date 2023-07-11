# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from pytest import MonkeyPatch
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.utils_assert import assert_status
from pytest_simcore.helpers.utils_envs import setenvs_from_dict


@pytest.fixture
def app_environment(app_environment: EnvVarsDict, monkeypatch: MonkeyPatch):
    return setenvs_from_dict(
        monkeypatch,
        {
            **app_environment,
            "WEBSERVER_ANNOUNCEMENTS": "1",
        },
    )


async def test_list_announcements(client: TestClient):
    assert client.app

    url = client.app.router["list_announcements"].url_for()

    response = await client.get(f"{url}")
    data, error = await assert_status(response, web.HTTPOk)
    assert error is None
    assert data == []

    # TODO: inject announcement in redis

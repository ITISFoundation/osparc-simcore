# pylint: disable=redefined-outer-name
# pylint: disable=protected-access
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import json
from typing import Any, AsyncIterator

import pytest
import redis.asyncio as aioredis
import simcore_service_webserver.announcements._models
from aiohttp import web
from aiohttp.test_utils import TestClient
from pydantic import BaseModel, parse_obj_as
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.utils_assert import assert_status
from pytest_simcore.helpers.utils_envs import setenvs_from_dict
from pytest_simcore.pydantic_models import iter_model_examples_in_module
from simcore_service_webserver.announcements._redis import _REDISKEYNAME, Announcement


@pytest.fixture
def app_environment(app_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch):
    return app_environment | setenvs_from_dict(
        monkeypatch,
        {
            "WEBSERVER_DB_LISTENER": "0",
            "WEBSERVER_GARBAGE_COLLECTOR": "null",
            "WEBSERVER_ANNOUNCEMENTS": "1",
        },
    )


@pytest.mark.parametrize(
    "model_cls, example_name, example_data",
    iter_model_examples_in_module(
        simcore_service_webserver.announcements._models  # noqa: SLF001
    ),
)
def test_model_examples(
    model_cls: type[BaseModel], example_name: int, example_data: Any
):
    assert model_cls.parse_obj(
        example_data
    ), f"Failed {example_name} : {json.dumps(example_data)}"


async def test_list_announcements(client: TestClient):
    assert client.app

    # checks route defined
    url = client.app.router["list_announcements"].url_for()

    # check no announcements
    response = await client.get(f"{url}")
    data, error = await assert_status(response, web.HTTPOk)
    assert error is None
    assert data == []

    # TODO: inject announcement in redis


@pytest.fixture
async def fake_announcements(
    redis_client: aioredis.Redis, count: int
) -> AsyncIterator[list[Announcement]]:
    announcements = parse_obj_as(
        list[Announcement], Announcement.Config.schema_extra["examples"]
    )
    for example in announcements:
        await redis_client.lpush(_REDISKEYNAME, example)

    yield announcements

    await redis_client.flushall()


async def test_list_announcements_for_product_and_not_expired(
    client: TestClient, fake_announcements: list[Announcement]
):
    assert fake_announcements

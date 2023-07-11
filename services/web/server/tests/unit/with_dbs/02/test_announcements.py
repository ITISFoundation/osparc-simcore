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
from settings_library.redis import RedisDatabase, RedisSettings
from simcore_service_webserver.announcements._redis import _REDIS_KEYNAME, Announcement


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
    redis_service: RedisSettings,
) -> AsyncIterator[list[dict[str, Any]]]:
    r = aioredis.from_url(
        redis_service.build_redis_dsn(RedisDatabase.ANNOUNCEMENTS),
        decode_responses=True,
    )

    got1 = await r.lrange(_REDIS_KEYNAME, 0, -1)
    got2 = await r.get(name=_REDIS_KEYNAME)

    values = [
        {
            "id": "Student_Competition_2023",
            "products": ["s4llite", "osparc"],
            "start": "2023-06-22T15:00:00.000Z",
            "end": "2023-11-01T02:00:00.000Z",
            "title": "Student Competition 2023",
            "description": "For more information click <a href='https://zmt.swiss/news-and-events/news/sim4life/s4llite-student-competition-2023/' style='color: white' target='_blank'>here</a>",
            "link": "https://zmt.swiss/news-and-events/news/sim4life/s4llite-student-competition-2023/",
            "widgets": ["login", "ribbon"],
        },
        {
            "id": "TIP_v2",
            "products": ["tis"],
            "start": "2023-07-22T15:00:00.000Z",
            "end": "2023-08-01T02:00:00.000Z",
            "title": "TIP v2",
            "description": "For more information click <a href='https://itis.swiss/tools-and-systems/ti-planning/' style='color: white' target='_blank'>here</a>",
            "link": "https://itis.swiss/tools-and-systems/ti-planning/",
            "widgets": ["login", "ribbon", "user-menu"],
        },
    ]

    await r.lpush(_REDIS_KEYNAME, *[json.dumps(v) for v in values])

    yield values

    await r.flushall()


@pytest.mark.testit
async def test_list_announcements_for_product_and_not_expired(
    client: TestClient, fake_announcements: dict[str, Any]
):
    assert fake_announcements
    all_announcements = parse_obj_as(list[Announcement], fake_announcements)

    assert client.app

    # checks route defined
    url = client.app.router["list_announcements"].url_for()

    # check no announcements
    response = await client.get(f"{url}")
    data, error = await assert_status(response, web.HTTPOk)
    assert error is None
    assert data == [a.dict() for a in all_announcements if "osparc" in a.products]

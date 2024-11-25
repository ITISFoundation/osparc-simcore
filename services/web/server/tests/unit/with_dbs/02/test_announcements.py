# pylint: disable=redefined-outer-name
# pylint: disable=protected-access
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import json
from collections.abc import AsyncIterator, Callable
from copy import deepcopy
from typing import Any

import arrow
import pytest
import redis.asyncio as aioredis
import simcore_service_webserver.announcements._models
from aiohttp.test_utils import TestClient
from faker import Faker
from pydantic import BaseModel, ValidationError
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.pydantic_models import iter_model_examples_in_module
from servicelib.aiohttp import status
from settings_library.redis import RedisDatabase, RedisSettings
from simcore_service_webserver.announcements._redis import (
    _PUBLIC_ANNOUNCEMENTS_REDIS_KEY,
    Announcement,
)

_TEXT_FORMAT = "YYYY-MM-DDTHH:mm:ss+00:00"


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


@pytest.fixture
async def push_announcements_in_redis(
    redis_service: RedisSettings,
) -> AsyncIterator[Callable]:
    ar = aioredis.from_url(
        redis_service.build_redis_dsn(RedisDatabase.ANNOUNCEMENTS),
        decode_responses=True,
    )

    async def _push(values: list[Any]) -> list[str]:
        items = [v if isinstance(v, str) else json.dumps(v) for v in values]
        count = await ar.lpush(_PUBLIC_ANNOUNCEMENTS_REDIS_KEY, *items)
        assert count == len(values)

        return items

    yield _push

    await ar.flushall()


async def test_list_empty_announcements(client: TestClient):
    assert client.app

    # checks route defined
    url = client.app.router["list_announcements"].url_for()

    # check no announcements
    response = await client.get(f"{url}")
    data, error = await assert_status(response, status.HTTP_200_OK)
    assert error is None
    assert data == []


async def test_list_announcements(
    client: TestClient, push_announcements_in_redis: Callable, faker: Faker
):
    assert client.app

    # redis one item
    now = arrow.utcnow()
    expected = [
        {
            "id": "Student_Competition_2023",
            "products": ["s4llite", "osparc"],
            "start": now.format(_TEXT_FORMAT),
            "end": now.shift(hours=1).format(_TEXT_FORMAT),
            "title": "Student Competition 2023",
            "description": "foo",
            "link": faker.url(),
            "widgets": ["login", "ribbon"],
        }
    ]
    await push_announcements_in_redis(expected)

    # checks route defined
    url = client.app.router["list_announcements"].url_for()

    # check no announcements
    response = await client.get(f"{url}")
    data, error = await assert_status(response, status.HTTP_200_OK)
    assert error is None
    assert data == expected


async def test_list_announcements_filtered(
    client: TestClient, push_announcements_in_redis: Callable, faker: Faker
):
    assert client.app
    now = arrow.utcnow()

    # redis multiple items
    expected = [
        {
            "id": "Student_Competition_2023",
            "products": ["s4llite", "osparc"],
            "start": now.format(_TEXT_FORMAT),
            "end": now.shift(hours=1).format(_TEXT_FORMAT),
            "title": "Student Competition 2023",
            "description": "foo",
            "link": faker.url(),
            "widgets": ["login", "ribbon"],
        }
    ]

    other_product = {
        "id": "TIP_v2",
        "products": ["tis"],
        "start": now.format(_TEXT_FORMAT),
        "end": now.shift(hours=1).format(_TEXT_FORMAT),
        "title": "TIP v2",
        "description": faker.text(),
        "link": faker.url(),
        "widgets": ["login", "ribbon", "user-menu"],
    }

    expired = deepcopy(expected[0])
    expired.update(
        {
            "id": "Student_Competition_2022",
            "start": now.shift(years=-1).format(_TEXT_FORMAT),
            "end": now.shift(years=-1, hours=1).format(_TEXT_FORMAT),
        }
    )

    invalid = deepcopy(expected[0])
    invalid.update(
        {
            "id": "Invalid_item",
            "start": now.format(),
            "end": now.shift(hours=-1).format(_TEXT_FORMAT),
        }
    )

    await push_announcements_in_redis(
        values=[*expected, other_product, expired, invalid]
    )

    # checks route defined
    url = client.app.router["list_announcements"].url_for()

    # check no announcements
    response = await client.get(f"{url}")
    data, error = await assert_status(response, status.HTTP_200_OK)
    assert error is None
    assert data == expected


#
# test_announcements_model.py
#


@pytest.mark.parametrize(
    "model_cls, example_name, example_data",
    iter_model_examples_in_module(
        simcore_service_webserver.announcements._models  # noqa: SLF001
    ),
)
def test_model_examples(
    model_cls: type[BaseModel], example_name: int, example_data: Any
):
    assert model_cls.model_validate(
        example_data
    ), f"Failed {example_name} : {json.dumps(example_data)}"


def test_invalid_announcement(faker: Faker):
    now = arrow.utcnow()
    with pytest.raises(ValidationError):
        Announcement.model_validate(
            {
                "id": "Student_Competition_2023",
                "products": ["s4llite", "osparc"],
                "start": now.format(),
                "end": now.shift(hours=-1).format(),
                "title": "Student Competition 2023",
                "description": faker.text(),
                "link": faker.url(),
                "widgets": ["login", "ribbon"],
            }
        )


def test_announcement_expired(faker: Faker):
    now = arrow.utcnow()
    model = Announcement.model_validate(
        {
            "id": "Student_Competition_2023",
            "products": ["s4llite", "osparc"],
            "start": now.shift(hours=-2).format(),
            "end": now.shift(hours=-1).format(),
            "title": "Student Competition 2023",
            "description": faker.text(),
            "link": faker.url(),
            "widgets": ["login", "ribbon"],
        }
    )
    assert model.expired()

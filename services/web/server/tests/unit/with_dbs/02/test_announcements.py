# pylint: disable=redefined-outer-name
# pylint: disable=protected-access
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import json
from typing import Any

import pytest
import simcore_service_webserver.announcements._models
from aiohttp import web
from aiohttp.test_utils import TestClient
from pydantic import BaseModel
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.utils_assert import assert_status
from pytest_simcore.helpers.utils_envs import setenvs_from_dict
from pytest_simcore.pydantic_models import iter_model_examples_in_module


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

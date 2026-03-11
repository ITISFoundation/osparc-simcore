# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements

import json
from collections.abc import Iterator

import httpx
import pytest
import respx
from aiohttp.test_utils import TestClient
from pytest_mock import MockerFixture
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_service_webserver.fogbugz._client import (
    FogbugzCaseCreate,
    get_fogbugz_rest_client,
)
from simcore_service_webserver.fogbugz.settings import FogbugzSettings


@pytest.fixture
def fake_api_base_url() -> str:
    return "https://dummy.com"


@pytest.fixture
def app_environment(
    monkeypatch: pytest.MonkeyPatch,
    app_environment: EnvVarsDict,
    fake_api_base_url: str,
    mocker: MockerFixture,
):
    return app_environment | setenvs_from_dict(
        monkeypatch,
        {
            "FOGBUGZ_URL": fake_api_base_url,
            "FOGBUGZ_API_TOKEN": "asdf",
        },
    )


_IXBUG_DUMMY = "12345"


@pytest.fixture
def mock_fogbugz_api(fake_api_base_url: str) -> Iterator[respx.MockRouter]:
    """Mock Fogbugz API responses in sequence for the test flow"""

    # Define responses in the order they will be called during the test
    responses = [
        # 1. create_case response
        {"data": {"case": {"ixBug": _IXBUG_DUMMY}}},
        # 2. get_case_status response (after creation)
        {"data": {"cases": [{"ixBug": _IXBUG_DUMMY, "sStatus": "Active"}]}},
        # 3. resolve_case response
        {"data": {}},
        # 4. get_case_status response (after resolve)
        {"data": {"cases": [{"ixBug": _IXBUG_DUMMY, "sStatus": "Resolved (Completed)"}]}},
        # 5. reopen_case response (inside you need to get the status ones)
        {"data": {"cases": [{"ixBug": _IXBUG_DUMMY, "sStatus": "Resolved (Completed)"}]}},
        {"data": {}},
        # 6. get_case_status response (after reopen)
        {"data": {"cases": [{"ixBug": _IXBUG_DUMMY, "sStatus": "Active"}]}},
    ]

    with respx.mock(base_url=fake_api_base_url) as mock:
        # Create a side_effect that returns responses in sequence
        mock.post(path="/f/api/0/jsonapi").mock(
            side_effect=[httpx.Response(200, json=response) for response in responses]
        )
        yield mock


async def test_fogubugz_client(
    app_environment: EnvVarsDict,
    client: TestClient,
    mock_fogbugz_api: respx.MockRouter,
):
    assert client.app

    settings = FogbugzSettings.create_from_envs()
    assert settings.FOGBUGZ_API_TOKEN

    fogbugz_client = get_fogbugz_rest_client(client.app)
    assert fogbugz_client

    _json = {"first_key": "test", "second_key": "test2"}
    _description = f"""
    Dear Support Team,

    We have received a support request.

    Extra content: {json.dumps(_json)}
    """

    case_id = await fogbugz_client.create_case(
        data=FogbugzCaseCreate(
            fogbugz_project_id=45,
            title="Matus Test Automatic Creation of Fogbugz Case",
            description=_description,
        )
    )
    assert case_id == _IXBUG_DUMMY

    status = await fogbugz_client.get_case_status(case_id)
    assert status == "Active"

    await fogbugz_client.resolve_case(case_id)
    status = await fogbugz_client.get_case_status(case_id)
    assert status == "Resolved (Completed)"

    await fogbugz_client.reopen_case(
        case_id,
        assigned_fogbugz_person_id="281",
        reopen_msg="Reopening the case with customer request",
    )
    status = await fogbugz_client.get_case_status(case_id)
    assert status == "Active"

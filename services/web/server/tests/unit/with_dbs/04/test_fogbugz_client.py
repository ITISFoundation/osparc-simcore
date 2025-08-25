import pytest
from aiohttp.test_utils import TestClient
from pytest_mock import MockerFixture
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from servicelib.aiohttp import status
from simcore_service_webserver.fogbugz._client import (
    FogbugzCaseCreate,
    get_fogbugz_rest_client,
)
from simcore_service_webserver.fogbugz.settings import FogbugzSettings

# @pytest.fixture(scope="session")
# def fake_api_base_url() -> str:
#     return "https://testserver-itis-vip.xyz"


# @pytest.fixture
# def mock_fogbugz_api(
#     faker: Faker, fake_api_base_url: str
# ) -> Iterator[respx.MockRouter]:
#     response_data = {
#         "msg": 0,
#         "availableDownloads": [
#             random_itis_vip_available_download_item(
#                 identifier=i,
#                 features_functionality="Posable",
#                 fake=faker,
#             )
#             for i in range(8)
#         ],
#     }

#     with respx.mock(base_url=fake_api_base_url) as mock:
#         mock.post(path__regex=r"/getDownloadableItems/(?P<category>\w+)").respond(
#             status_code=200, json=response_data
#         )
#         yield mock


@pytest.fixture
def app_environment(
    monkeypatch: pytest.MonkeyPatch,
    app_environment: EnvVarsDict,
    # fake_api_base_url: str,
    mocker: MockerFixture,
):
    return app_environment | setenvs_from_dict(
        monkeypatch,
        {
            "FOGBUGZ_URL": "https://dummy.com",
            "FOGBUGZ_API_TOKEN": "12345",
        },
    )


async def test_testit(
    app_environment: EnvVarsDict,
    # mock_fogbugz_api: respx.MockRouter,
    client: TestClient,
):
    assert client.app

    settings = FogbugzSettings.create_from_envs()
    assert settings.FOGBUGZ_API_TOKEN

    fogbugz_client = get_fogbugz_rest_client(client.app)
    assert fogbugz_client

    case_id = await fogbugz_client.create_case(
        data=FogbugzCaseCreate(
            fogbugz_project_id="45",
            title="Matus Test Automatic Creation of Fogbugz Case",
            description="This is a test case",
        )
    )
    assert case_id

    status = await fogbugz_client.get_case_status(case_id)
    assert status == "Active"

    await fogbugz_client.resolve_case(case_id)
    status = await fogbugz_client.get_case_status(case_id)
    assert status == "Resolved (Completed)"

    await fogbugz_client.reopen_case(case_id, assigned_fogbugz_person_id="281")
    status = await fogbugz_client.get_case_status(case_id)
    assert status == "Active"

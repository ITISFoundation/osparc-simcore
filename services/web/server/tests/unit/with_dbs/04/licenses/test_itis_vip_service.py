# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import logging
from collections.abc import Iterator

import pytest
import respx
from aiohttp.test_utils import TestClient
from faker import Faker
from httpx import AsyncClient
from models_library.licensed_items import LicensedResourceType
from pydantic import ValidationError
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from servicelib.aiohttp import status
from simcore_service_webserver.licenses import (
    _itis_vip_service,
    _itis_vip_syncer_service,
    _licensed_items_service,
)
from simcore_service_webserver.licenses._itis_vip_models import (
    ItisVipData,
    _feature_descriptor_to_dict,
)
from simcore_service_webserver.licenses._itis_vip_service import ItisVipApiResponse
from simcore_service_webserver.licenses._itis_vip_settings import ItisVipSettings
from simcore_service_webserver.licenses._licensed_items_service import RegistrationState


def test_pre_validator_feature_descriptor_to_dict():
    # Makes sure the regex used here, which is vulnerable to polynomial runtime due to backtracking, cannot lead to denial of service.
    with pytest.raises(ValidationError) as err_info:
        _feature_descriptor_to_dict("a" * 10000 + ": " + "b" * 10000)
    assert err_info.value.errors()[0]["type"] == "string_too_long"


@pytest.fixture(scope="session")
def fake_api_base_url() -> str:
    return "https://testserver-itis-vip.xyz"


@pytest.fixture
def app_environment(
    monkeypatch: pytest.MonkeyPatch,
    app_environment: EnvVarsDict,
    fake_api_base_url: str,
):
    return app_environment | setenvs_from_dict(
        monkeypatch,
        {
            "ITIS_VIP_API_URL": f"{fake_api_base_url}/PD_DirectDownload/getDownloadableItems/{{category}}",
            # NOTE: ItisVipSettings will decode with json.dumps(). Use " and not ' the json keys!!
            "ITIS_VIP_CATEGORIES": '{"ComputationalPantom": "Phantoms", "HumanBodyRegion": "Humans (Regions)"}',
        },
    )


@pytest.fixture
def mock_itis_vip_downloadables_api(
    faker: Faker, fake_api_base_url: str
) -> Iterator[respx.MockRouter]:
    response_data = {
        "msg": 0,
        "availableDownloads": [
            {
                "ID": i,
                "Description": faker.sentence(),
                "Thumbnail": faker.image_url(),
                # NOTE: this is manually added in the server side so be more robust to errors
                "Features": f"{{name: {faker.name()} Right Hand, version: V{faker.pyint()}.0, sex: Male, age: 8 years,date: {faker.date()}, ethnicity: Caucasian, functionality: Posable}}",
                "DOI": faker.bothify(text="10.####/ViP#####-##-#"),
                "LicenseKey": faker.bothify(text="MODEL_????_V#"),
                "LicenseVersion": faker.bothify(text="V#.0"),
                "Protection": faker.random_element(elements=["Code", "PayPal"]),
                "AvailableFromURL": faker.random_element(elements=[None, faker.url()]),
            }
            for i in range(8)
        ],
    }

    with respx.mock(base_url=fake_api_base_url) as mock:
        mock.post(path__regex=r"/getDownloadableItems/(?P<category>\w+)").respond(
            status_code=200, json=response_data
        )
        yield mock


async def test_fetch_and_validate_itis_vip_api(
    mock_itis_vip_downloadables_api: respx.MockRouter, fake_api_base_url: str
):
    async with AsyncClient(base_url=fake_api_base_url) as client:
        response = await client.post("/getDownloadableItems/ComputationalPantom")
        assert response.status_code == status.HTTP_200_OK
        response_json = response.json()

        try:
            validated_data = ItisVipApiResponse(**response_json)
        except ValidationError as e:
            pytest.fail(f"Response validation failed: {e}")

        assert validated_data.msg == 0
        assert len(validated_data.available_downloads) == 8

        assert (
            validated_data.available_downloads[0].features.get("functionality")
            == "Posable"
        )

        print(validated_data.model_dump_json(indent=1))


async def test_get_category_items(
    mock_itis_vip_downloadables_api: respx.MockRouter,
    app_environment: EnvVarsDict,
):
    settings = ItisVipSettings.create_from_envs()
    assert settings.ITIS_VIP_CATEGORIES

    async with AsyncClient() as client:
        for url, category in zip(
            settings.get_urls(), settings.ITIS_VIP_CATEGORIES, strict=True
        ):
            assert f"{url}".endswith(category)

            items = await _itis_vip_service.get_category_items(client, url)

            assert items[0].features.get("functionality") == "Posable"


async def test_sync_itis_vip_as_licensed_items(
    mock_itis_vip_downloadables_api: respx.MockRouter,
    app_environment: EnvVarsDict,
    client: TestClient,
    ensure_empty_licensed_items: None,
):
    assert client.app

    settings = ItisVipSettings.create_from_envs()
    assert settings.ITIS_VIP_CATEGORIES

    async with AsyncClient() as http_client:
        for url, category in zip(
            settings.get_urls(), settings.ITIS_VIP_CATEGORIES, strict=True
        ):
            assert f"{url}".endswith(category)

            vip_resources: list[
                ItisVipData
            ] = await _itis_vip_service.get_category_items(http_client, url)
            assert vip_resources[0].features.get("functionality") == "Posable"

            for vip in vip_resources:

                # register a NEW resource
                (
                    licensed_item1,
                    state1,
                    _,
                ) = await _licensed_items_service.register_resource_as_licensed_item(
                    client.app,
                    licensed_resource_name=f"{category}/{vip.id}",
                    licensed_resource_type=LicensedResourceType.VIP_MODEL,
                    licensed_resource_data=vip,
                    licensed_item_display_name="foo",
                )
                assert state1 == RegistrationState.NEWLY_REGISTERED

                # register the SAME resource
                (
                    licensed_item2,
                    state2,
                    _,
                ) = await _licensed_items_service.register_resource_as_licensed_item(
                    client.app,
                    licensed_resource_name=f"{category}/{vip.id}",
                    licensed_resource_type=LicensedResourceType.VIP_MODEL,
                    licensed_resource_data=vip,
                    licensed_item_display_name="foo",
                )

                assert state2 == RegistrationState.ALREADY_REGISTERED
                assert licensed_item1 == licensed_item2

                # register a MODIFIED version of the same resource
                (
                    licensed_item3,
                    state3,
                    msg,
                ) = await _licensed_items_service.register_resource_as_licensed_item(
                    client.app,
                    licensed_resource_name=f"{category}/{vip.id}",
                    licensed_resource_type=LicensedResourceType.VIP_MODEL,
                    licensed_resource_data=vip.model_copy(
                        update={
                            "features": {
                                **vip.features,
                                "functionality": "Non-Posable",
                            }
                        }
                    ),
                    licensed_item_display_name="foo",
                )
                assert state3 == RegistrationState.DIFFERENT_RESOURCE
                assert licensed_item2 == licensed_item3
                # {'values_changed': {"root['features']['functionality']": {'new_value': 'Non-Posable', 'old_value': 'Posable'}}}
                assert "functionality" in msg


async def test_itis_vip_syncer_service(
    mock_itis_vip_downloadables_api: respx.MockRouter,
    app_environment: EnvVarsDict,
    client: TestClient,
    caplog: pytest.LogCaptureFixture,
    ensure_empty_licensed_items: None,
):
    assert client.app

    settings = ItisVipSettings.create_from_envs()
    assert settings.ITIS_VIP_CATEGORIES

    categories = settings.to_categories()

    with caplog.at_level(logging.DEBUG, _itis_vip_syncer_service._logger.name):

        def _get_captured_levels():
            return [
                rc[1]
                for rc in caplog.record_tuples
                if rc[0] == _itis_vip_syncer_service._logger.name
            ]

        # one round
        caplog.clear()
        await _itis_vip_syncer_service.sync_resources_with_licensed_items(
            client.app, categories
        )
        levels_logged = _get_captured_levels()
        assert logging.DEBUG not in levels_logged
        assert logging.INFO in levels_logged
        assert logging.WARNING not in levels_logged

        caplog.clear()
        # second round
        await _itis_vip_syncer_service.sync_resources_with_licensed_items(
            client.app, categories
        )

        levels_logged = _get_captured_levels()
        assert logging.DEBUG in levels_logged
        assert logging.INFO not in levels_logged
        assert logging.WARNING not in levels_logged

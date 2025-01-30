# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements

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
    _licensed_items_service,
)
from simcore_service_webserver.licenses._itis_vip_models import (
    AvailableDownload,
    _feature_descriptor_to_dict,
)
from simcore_service_webserver.licenses._itis_vip_service import ResponseData
from simcore_service_webserver.licenses._itis_vip_settings import ItisVipSettings


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
            "ITIS_VIP_CATEGORIES": '["ComputationalPantom","FooCategory","BarCategory"]',  # NOTE: ItisVipSettings will decode with json.dumps()
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
            validated_data = ResponseData(**response_json)
        except ValidationError as e:
            pytest.fail(f"Response validation failed: {e}")

        assert validated_data.msg == 0
        assert len(validated_data.available_downloads) == 8

        assert (
            validated_data.available_downloads[0].features["functionality"] == "Posable"
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

            assert items[0].features["functionality"] == "Posable"


async def test_sync_itis_vip_as_licensed_items(
    mock_itis_vip_downloadables_api: respx.MockRouter,
    app_environment: EnvVarsDict,
    client: TestClient,
):
    assert client.app

    settings = ItisVipSettings.create_from_envs()
    assert settings.ITIS_VIP_CATEGORIES

    async with AsyncClient() as http_client:
        for url, category in zip(
            settings.get_urls(), settings.ITIS_VIP_CATEGORIES, strict=True
        ):
            assert f"{url}".endswith(category)

            items: list[AvailableDownload] = await _itis_vip_service.get_category_items(
                http_client, url
            )
            assert items[0].features["functionality"] == "Posable"

            for vip_item in items:
                (
                    got1,
                    state1,
                ) = await _licensed_items_service.register_resource_as_licensed_item(
                    client.app,
                    licensed_resource_name=f"{category}/{vip_item.id}",
                    licensed_resource_type=LicensedResourceType.VIP_MODEL,
                    licensed_resource_data=vip_item,
                    license_key=vip_item.license_key,
                )
                assert (
                    state1 == _licensed_items_service.RegistrationState.NEWLY_REGISTERED
                )

                (
                    got2,
                    state2,
                ) = await _licensed_items_service.register_resource_as_licensed_item(
                    client.app,
                    licensed_resource_name=f"{category}/{vip_item.id}",
                    licensed_resource_type=LicensedResourceType.VIP_MODEL,
                    licensed_resource_data=vip_item,
                    license_key=vip_item.license_key,
                )

                assert (
                    state2
                    == _licensed_items_service.RegistrationState.ALREADY_REGISTERED
                )
                assert got1 == got2

                # Modify vip_item and register again
                vip_item_modified = vip_item.model_copy(
                    update={
                        "features": {
                            **vip_item.features,
                            "functionality": "Non-Posable",
                        }
                    }
                )
                (
                    got3,
                    state3,
                ) = await _licensed_items_service.register_resource_as_licensed_item(
                    client.app,
                    licensed_resource_name=f"{category}/{vip_item.id}",
                    licensed_resource_type=LicensedResourceType.VIP_MODEL,
                    licensed_resource_data=vip_item_modified,
                    license_key=vip_item.license_key,
                )

                assert (
                    state3
                    == _licensed_items_service.RegistrationState.DIFFERENT_RESOURCE
                )
                # not stored!
                assert got2 == got3

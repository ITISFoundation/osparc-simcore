# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements

from collections.abc import Iterator

import pytest
import respx
from faker import Faker
from httpx import AsyncClient
from pydantic import ValidationError
from servicelib.aiohttp import status
from simcore_service_webserver.licenses._itis_vip_service import ResponseData


@pytest.fixture
def mock_itis_vip_downloadables_api(faker: Faker) -> Iterator[respx.MockRouter]:
    api_url = "http://testserver"
    response_data = {
        "msg": 0,
        "availableDownloads": [
            {
                "ID": faker.random_int(min=70, max=90),
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
            for _ in range(8)
        ],
    }

    with respx.mock(base_url=api_url) as mock:
        mock.post("getDownloadableItems/ComputationalPantom").respond(
            status_code=200, json=response_data
        )
        yield mock


async def test_fetch_itis_vip_api(
    mock_itis_vip_downloadables_api: respx.MockRouter,
):
    async with AsyncClient(base_url="http://testserver") as client:
        response = await client.post("getDownloadableItems/ComputationalPantom")
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

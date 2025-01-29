import re
from typing import Annotated, Any, Iterator, Literal

import pytest
import respx
from faker import Faker
from httpx import AsyncClient
from pydantic import BaseModel, Field, HttpUrl, ValidationError
from servicelib.aiohttp import status


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
                "Features": f"{{name: {faker.name()} Right Hand, version: V{faker.pyint()}.0, sex: {faker.gender()}, age: {faker.age()} years,date: {faker.date()}, ethnicity: Caucasian, functionality: Posable}}",
                "DOI": None,
                "LicenseKey": faker.bothify(text="MODEL_????_V#"),
                "LicenseVersion": "V1.0",
                "Protection": "Code",
                "AvailableFromURL": None,
            }
            for _ in range(8)
        ],
    }

    with respx.mock(base_url=api_url) as mock:
        mock.post("getDownloadableItems/ComputationalPantom").respond(
            status_code=200, json=response_data
        )
        yield mock


def descriptor_to_dict(descriptor: str) -> dict[str, Any]:
    pattern = r"(\w+): ([^,]+)"
    matches = re.findall(pattern, descriptor)
    return {key: value for key, value in matches}


class AvailableDownload(BaseModel):
    id: Annotated[int, Field(alias="ID")]
    description: Annotated[str, Field(alias="Description")]
    thumbnail: Annotated[str, Field(alias="Thumbnail")]
    features: Annotated[dict[str, Any], Field(alias="Features")]
    doi: Annotated[str, Field(alias="DOI")]
    license_key: Annotated[str | None, Field(alias="LicenseKey")]
    license_version: Annotated[str | None, Field(alias="LicenseVersion")]
    protection: Annotated[Literal["Code", "PayPal"], Field(alias="Protection")]
    available_from_url: Annotated[HttpUrl | None, Field(alias="AvailableFromURL")]


class ResponseData(BaseModel):
    msg: int = -1
    available_downloads: Annotated[
        list[AvailableDownload], Field(alias="availableDownloads")
    ]


async def test_computational_pantom_api(
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
        assert len(validated_data.availableDownloads) == 8

        assert (
            validated_data.availableDownloads[0].Features["functionality"] == "Posable"
        )

        print(validated_data.model_dump_json())

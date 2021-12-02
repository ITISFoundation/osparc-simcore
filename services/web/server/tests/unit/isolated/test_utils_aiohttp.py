import json
from typing import Any, Dict
from uuid import UUID

import pytest
from aiohttp import web
from faker import Faker
from pydantic import BaseModel
from simcore_service_webserver.utils_aiohttp import envelope_json_response


@pytest.fixture
def data(faker: Faker) -> Dict[str, Any]:
    class Point(BaseModel):
        x: int
        y: int
        uuid: UUID

    return {
        "str": faker.word(),
        "float": faker.pyfloat(),
        "int": faker.pyint(),
        "object-pydantic": Point(x=faker.pyint(), y=faker.pyint(), uuid=faker.uuid4()),
        "object": {"name": faker.name(), "surname": faker.name()},
    }


def test_enveloped_successful_response(data: Dict):
    resp = envelope_json_response(data, web.HTTPCreated)
    assert resp.text is not None

    resp_body = json.loads(resp.text)
    assert {"data"} == set(resp_body.keys())


def test_enveloped_failing_response():

    resp = envelope_json_response(
        {"message": "could not find it", "reason": "invalid id"}, web.HTTPNotFound
    )
    assert resp.text is not None

    assert {"error"} == set(json.loads(resp.text).keys())

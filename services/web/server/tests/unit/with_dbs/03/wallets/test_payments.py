# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


import json
from pathlib import Path
from typing import Any, TypeAlias

import arrow
import jsonref
import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from faker import Faker
from models_library.utils.fastapi_encoders import jsonable_encoder
from pytest_simcore.aioresponses_mocker import AioResponsesMock
from pytest_simcore.helpers.utils_assert import assert_status
from pytest_simcore.helpers.utils_login import UserInfoDict
from toolz.dicttoolz import get_in
from yarl import URL

OpenApiDict: TypeAlias = dict[str, Any]


@pytest.fixture
def payments_service_openapi_specs(osparc_simcore_services_dir: Path) -> OpenApiDict:
    oas = jsonref.replace_refs(
        json.loads(
            (osparc_simcore_services_dir / "payments" / "openapi.json").read_text()
        )
    )
    assert isinstance(oas, dict)
    return oas


@pytest.fixture
def mock_payments_service_http_api(
    aioresponses_mocker: AioResponsesMock,
    payments_service_openapi_specs: dict[str, Any],
    base_url: URL,
) -> AioResponsesMock:
    """Mocks responses from payments service API"""
    oas = payments_service_openapi_specs

    # healthcheck
    assert "/" in oas["paths"]
    aioresponses_mocker.get(
        f"{base_url}/",
        status=web.HTTPOk.status_code,
        repeat=False,  # NOTE: this is only usable once!
    )

    # meta
    assert "/v1/meta" in oas["paths"]
    schema = get_in(
        [
            "paths",
            "/v1/meta",
            "get",
            "responses",
            "200",
            "content",
            "application/json",
            "schema",
        ],
        oas,
        no_default=True,
    )
    assert isinstance(schema, dict)

    aioresponses_mocker.get(
        f"{base_url}/v1/meta",
        status=web.HTTPOk.status_code,
        payload=jsonable_encoder(schema["example"]),
    )

    # create payment started
    assert "/v1/payments" in oas["paths"]
    aioresponses_mocker.post(
        f"{base_url}/v1/payments",
        status=web.HTTPOk.status_code,
        payload=jsonable_encoder(
            {
                "payment_id": 1234,
                "status": "CREATED",
                "updated": arrow.now(),
            }
        ),
    )

    return aioresponses_mocker


async def test_payments_worfklow(
    client: TestClient,
    faker: Faker,
    logged_user: UserInfoDict,
):
    assert client.app

    wallet_id = 123

    response = await client.post(
        f"/v0/wallet/{wallet_id}/payments",
        json={
            # "product_id": "osparc" -> headers
            # "user_id": 1, -> auth
            "wallet_id": wallet_id,
            "credits": 50,
            "amount_total": {"value": 25, "currency": "dollars"},
        },
    )

    data, error = await assert_status(response, web.HTTPCreated)
    assert data == {"id": 1234, "status": "CREATED", "submission_url": faker.url()}
    assert error is None

    # some time later
    # payment gets acknoledged -> socketio
    # send to front-end
    # send email
    #

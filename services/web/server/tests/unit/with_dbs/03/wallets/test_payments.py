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
from models_library.api_schemas_webserver.wallets import PaymentGet, WalletGet
from models_library.utils.fastapi_encoders import jsonable_encoder
from models_library.wallets import PaymentTransactionState
from pydantic import parse_obj_as
from pytest_simcore.aioresponses_mocker import AioResponsesMock
from pytest_simcore.helpers.utils_assert import assert_status
from pytest_simcore.helpers.utils_login import UserInfoDict
from simcore_service_webserver.db.models import UserRole
from simcore_service_webserver.payments.api import get_payments_service_api
from simcore_service_webserver.payments.settings import (
    PaymentsSettings,
    get_plugin_settings,
)
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
def app_payments_plugin_settings(client: TestClient) -> PaymentsSettings:
    assert client.app
    settings = get_plugin_settings(app=client.app)
    assert settings
    return settings


@pytest.fixture
def mock_payments_service_http_api(
    aioresponses_mocker: AioResponsesMock,
    payments_service_openapi_specs: dict[str, Any],
    app_payments_plugin_settings: PaymentsSettings,
) -> AioResponsesMock:
    """Mocks responses from payments service API"""
    oas = payments_service_openapi_specs
    base_url = URL(app_payments_plugin_settings.base_url)

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


## ---------------------------------


async def test_plugin_payments_service_api(
    client: TestClient, mock_payments_service_http_api: AioResponsesMock
):
    assert client.app

    payments_service = get_payments_service_api(client.app)
    assert payments_service.is_healthy()

    #

    assert not payments_service.is_healthy()


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_payments_worfklow(
    client: TestClient, faker: Faker, logged_user: UserInfoDict, wallets_clean_db: None
):
    assert client.app

    # create a new wallet
    url = client.app.router["create_wallet"].url_for()
    resp = await client.post(
        url.path, json={"name": "My first wallet", "description": "Custom description"}
    )
    data, _ = await assert_status(resp, web.HTTPCreated)
    wallet = WalletGet.parse_obj(data)

    # pay with wallet
    response = await client.post(
        f"/v0/wallet/{wallet.wallet_id}/payments",
        json={
            "credits": 50,
            "prize": 25,  # dollars?
        },
    )

    data, error = await assert_status(response, web.HTTPCreated)
    assert error is None
    payment = PaymentGet.parse_obj(data)

    assert payment.state == PaymentTransactionState.CREATED
    assert payment.prize == 50
    assert payment.submission_link

    # some time later
    # payment gets acknoledged -> socketio

    # inspect payment in wallet
    response = await client.get(
        f"/v0/wallet/{wallet.wallet_id}/payments/{payment.idr}",
    )
    data, error = await assert_status(response, web.HTTPOk)
    assert error is None
    payment = PaymentGet.parse_obj(data)

    assert payment.state == PaymentTransactionState.COMPLETED

    # list all payment transactions of a wallet
    response = await client.get(f"/v0/wallet/{wallet.wallet_id}/payments")
    data, error = await assert_status(response, web.HTTPOk)

    assert parse_obj_as(list[PaymentGet], data) is not None

    # list all payment transactions in all my wallets
    response = await client.get("/v0/wallet/-/payments")
    data, error = await assert_status(response, web.HTTPOk)

    assert parse_obj_as(list[PaymentGet], data) is not None

    # check email was sent to user

# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from collections.abc import Callable
from typing import Any, TypeAlias

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from faker import Faker
from models_library.api_schemas_webserver.wallets import (
    PaymentTransaction,
    WalletGet,
    WalletPaymentCreated,
)
from models_library.rest_pagination import Page
from pydantic import parse_obj_as
from pytest_mock import MockerFixture
from pytest_simcore.helpers.utils_assert import assert_status
from pytest_simcore.helpers.utils_login import UserInfoDict
from simcore_service_webserver.db.models import UserRole

OpenApiDict: TypeAlias = dict[str, Any]


@pytest.fixture
def user_role():
    return UserRole.USER


@pytest.fixture
def create_new_wallet(client: TestClient, faker: Faker) -> Callable:
    assert client.app
    url = client.app.router["create_wallet"].url_for()

    async def _create():
        resp = await client.post(
            url.path,
            json={
                "name": f"wallet {faker.word()}",
                "description": "Fake wallet from create_new_wallet",
            },
        )
        data, _ = await assert_status(resp, web.HTTPCreated)
        return WalletGet.parse_obj(data)

    return _create


async def test_payment_on_invalid_wallet(
    client: TestClient,
    faker: Faker,
    logged_user: UserInfoDict,
    wallets_clean_db: None,
    create_new_wallet: Callable,
):
    assert client.app
    wallet = await create_new_wallet()

    # TODO: test other user's wallet
    invalid_wallet = 1234
    assert wallet.wallet_id != invalid_wallet

    response = await client.post(
        f"/v0/wallets/{invalid_wallet}/payments",
        json={
            "osparcCredits": 50,
            "priceDollars": 25,
        },
    )
    data, error = await assert_status(response, web.HTTPForbidden)
    assert data is None
    assert error


@pytest.mark.acceptance_test(
    "For https://github.com/ITISFoundation/osparc-simcore/issues/4657"
)
async def test_payments_worfklow(
    client: TestClient,
    logged_user: UserInfoDict,
    create_new_wallet: Callable,
    wallets_clean_db: None,
    mocker: MockerFixture,
):
    assert client.app
    mocker.patch(
        "simcore_service_webserver.payments._socketio.send_messages", autospec=True
    )

    wallet = await create_new_wallet()

    # TEST add payment to wallet
    response = await client.post(
        f"/v0/wallets/{wallet.wallet_id}/payments",
        json={
            "osparcCredits": 50,
            "priceDollars": 25,
        },
    )
    data, error = await assert_status(response, web.HTTPCreated)
    assert error is None
    payment = WalletPaymentCreated.parse_obj(data)

    assert payment.payment_id
    assert payment.payment_form_url.query
    assert payment.payment_form_url.query.endswith(payment.payment_id)

    # list all payment transactions in all my wallets
    response = await client.get("/v0/wallets/-/payments")
    data, error = await assert_status(response, web.HTTPOk)

    page = parse_obj_as(Page[PaymentTransaction], data)

    assert page.data
    assert page.meta.total == 1
    assert page.meta.offset == 0
    assert page.data[0].payment_id == payment.payment_id

    # TODO: test completed
    # some time later - > completed
    # payment gets acknoledged -> socketio
    # list payments and get completion
    #

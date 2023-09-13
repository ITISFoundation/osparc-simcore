# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from collections.abc import Callable

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from faker import Faker
from models_library.api_schemas_webserver.wallets import (
    PaymentMethodGet,
    PaymentMethodInit,
    WalletGet,
)
from pydantic import parse_obj_as
from pytest_mock import MockerFixture
from pytest_simcore.helpers.utils_assert import assert_status
from pytest_simcore.helpers.utils_login import UserInfoDict
from simcore_postgres_database.models.payments_methods import InitPromptAckFlowState
from simcore_service_webserver.db.models import UserRole
from simcore_service_webserver.payments._api import (
    complete_create_of_wallet_payment_method,
)
from simcore_service_webserver.payments.settings import (
    PaymentsSettings,
    get_plugin_settings,
)


@pytest.fixture
def user_role():
    # TODO: refactor to common conftest.py

    return UserRole.USER


@pytest.fixture
def create_new_wallet(client: TestClient, faker: Faker) -> Callable:
    # TODO: refactor to common conftest.py

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


@pytest.fixture
async def logged_user_wallet(
    client: TestClient,
    logged_user: UserInfoDict,
    wallets_clean_db: None,
    create_new_wallet: Callable,
) -> WalletGet:
    # TODO: refactor to common conftest.py
    assert client.app
    return await create_new_wallet()


async def test_payment_method_worfklow(
    client: TestClient,
    logged_user_wallet: WalletGet,
    mocker: MockerFixture,
):
    assert client.app
    settings: PaymentsSettings = get_plugin_settings(client.app)

    assert settings.PAYMENTS_FAKE_COMPLETION is False

    send_message = mocker.patch(
        "simcore_service_webserver.payments._socketio.send_messages", autospec=True
    )
    wallet = logged_user_wallet

    # init Create
    response = await client.post(
        f"/v0/wallets/{wallet.wallet_id}/payments-method:init",
    )
    data, error = await assert_status(response, web.HTTPCreated)
    assert error is None
    init = PaymentMethodInit.parse_obj(data)

    assert init.payment_method_id
    assert init.payment_method_form_url.query
    assert init.payment_method_form_url.query.endswith(init.payment_method_id)

    # Get: if I try to get the payment method here, it should fail since the flow is NOT acked!
    response = await client.get(
        f"/v0/wallets/{wallet.wallet_id}/payments-method/{init.payment_method_id}"
    )
    data, error = await assert_status(response, web.HTTPConflict)
    assert "complete" in error["errors"][0]["details"]

    # Ack
    await complete_create_of_wallet_payment_method(
        client.app,
        payment_method_id=init.payment_method_id,
        completion_state=InitPromptAckFlowState.SUCCESS,
        message="ACKED by test_add_payment_method_worfklow",
    )
    assert send_message.called
    send_message.assert_called_once()

    # Get
    response = await client.get(
        f"/v0/wallets/{wallet.wallet_id}/payments-method/{init.payment_method_id}"
    )
    data, _ = await assert_status(response, web.HTTPOk)
    payment_method = PaymentMethodGet(**data)
    assert payment_method.idr == init.payment_method_id

    # List
    response = await client.get(f"/v0/wallets/{wallet.wallet_id}/payments-method")
    data, _ = await assert_status(response, web.HTTPOk)

    wallet_payments_methods = parse_obj_as(list[PaymentMethodGet], data)
    assert wallet_payments_methods == [payment_method]

    # Delete
    response = await client.delete(
        f"/v0/wallets/{wallet.wallet_id}/payments-method/{init.payment_method_id}"
    )
    await assert_status(response, web.HTTPNoContent)

    response = await client.get(f"/v0/wallets/{wallet.wallet_id}/payments-method")
    data, _ = await assert_status(response, web.HTTPOk)
    assert not data

    # TODO: if you like to the new naming of entrypoints and models for the flow, make it uniform with payments
    # TODO:


async def test_init_and_cancel_payment_method(
    client: TestClient,
    logged_user_wallet: WalletGet,
    mocker: MockerFixture,
):
    wallet = logged_user_wallet

    # init Create
    response = await client.post(
        f"/v0/wallets/{wallet.wallet_id}/payments-method:init",
    )
    data, error = await assert_status(response, web.HTTPCreated)
    assert error is None
    init = PaymentMethodInit.parse_obj(data)

    # cancel Create
    response = await client.post(
        f"/v0/wallets/{wallet.wallet_id}/payments-method/{init.payment_method_id}:cancel",
    )
    await assert_status(response, web.HTTPNoContent)

    # Get -> not found
    response = await client.get(
        f"/v0/wallets/{wallet.wallet_id}/payments-method/{init.payment_method_id}"
    )
    await assert_status(response, web.HTTPNotFound)

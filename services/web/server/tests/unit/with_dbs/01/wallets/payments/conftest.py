# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from collections.abc import Callable, Iterator
from decimal import Decimal
from typing import Any, TypeAlias, cast
from unittest.mock import MagicMock

import pycountry
import pytest
import sqlalchemy as sa
from aiohttp import web
from aiohttp.test_utils import TestClient
from faker import Faker
from models_library.api_schemas_webserver.wallets import (
    PaymentID,
    PaymentMethodGet,
    PaymentMethodID,
    PaymentMethodInitiated,
    PaymentTransaction,
    WalletGet,
)
from models_library.basic_types import IDStr
from models_library.payments import UserInvoiceAddress
from models_library.products import ProductName, StripePriceID, StripeTaxRateID
from models_library.users import UserID
from models_library.wallets import WalletID
from pydantic import EmailStr, HttpUrl
from pytest_mock import MockerFixture
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.webserver_login import UserInfoDict
from servicelib.aiohttp import status
from simcore_postgres_database.models.payments_transactions import payments_transactions
from simcore_postgres_database.models.users_details import (
    users_pre_registration_details,
)
from simcore_service_webserver.db.models import UserRole
from simcore_service_webserver.payments._methods_api import (
    _fake_cancel_creation_of_wallet_payment_method,
    _fake_delete_wallet_payment_method,
    _fake_get_wallet_payment_method,
    _fake_init_creation_of_wallet_payment_method,
    _fake_list_wallet_payment_methods,
)
from simcore_service_webserver.payments._onetime_api import (
    _fake_cancel_payment,
    _fake_get_payment_invoice_url,
    _fake_get_payments_page,
    _fake_init_payment,
    _fake_pay_with_payment_method,
)
from simcore_service_webserver.payments.settings import (
    PaymentsSettings,
    get_plugin_settings,
)

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
        data, _ = await assert_status(resp, status.HTTP_201_CREATED)
        return WalletGet.model_validate(data)

    return _create


@pytest.fixture
async def logged_user_wallet(
    client: TestClient,
    logged_user: UserInfoDict,
    wallets_clean_db: None,
    create_new_wallet: Callable,
) -> WalletGet:
    assert client.app
    return await create_new_wallet()


@pytest.fixture
def payments_transactions_clean_db(postgres_db: sa.engine.Engine) -> Iterator[None]:
    with postgres_db.connect() as con:
        yield
        con.execute(payments_transactions.delete())


@pytest.fixture
def mock_rpc_payments_service_api(
    mocker: MockerFixture, faker: Faker, payments_transactions_clean_db: None
) -> dict[str, MagicMock]:
    async def _init(
        app: web.Application,
        *,
        amount_dollars: Decimal,
        target_credits: Decimal,
        product_name: str,
        wallet_id: WalletID,
        wallet_name: str,
        user_id: UserID,
        user_name: str,
        user_email: str,
        user_address: UserInvoiceAddress,
        stripe_price_id: StripePriceID,
        stripe_tax_rate_id: StripeTaxRateID,
        comment: str | None = None,
    ):
        return await _fake_init_payment(
            app,
            amount_dollars,
            target_credits,
            product_name,
            wallet_id,
            user_id,
            user_email,
            comment,
        )

    async def _cancel(
        app: web.Application,
        *,
        payment_id: PaymentID,
        user_id: UserID,
        wallet_id: WalletID,
    ):
        await _fake_cancel_payment(app, payment_id)

    async def _get_page(
        app: web.Application,
        *,
        user_id: UserID,
        product_name: ProductName,
        limit: int | None,
        offset: int | None,
    ):
        assert limit is not None
        assert offset is not None
        assert product_name is not None
        return await _fake_get_payments_page(app, user_id, limit, offset)

    #  payment-methods  ----
    async def _init_pm(
        app: web.Application,
        *,
        wallet_id: WalletID,
        wallet_name: IDStr,
        user_id: UserID,
        user_name: IDStr,
        user_email: EmailStr,
    ) -> PaymentMethodInitiated:
        settings: PaymentsSettings = get_plugin_settings(app)
        assert settings.PAYMENTS_FAKE_COMPLETION is False

        return await _fake_init_creation_of_wallet_payment_method(
            app, settings, user_id, wallet_id
        )

    async def _cancel_pm(
        app: web.Application,
        *,
        payment_method_id: PaymentMethodID,
        user_id: UserID,
        wallet_id: WalletID,
    ) -> None:
        await _fake_cancel_creation_of_wallet_payment_method(
            app, payment_method_id, user_id, wallet_id
        )

    async def _list_pm(
        app: web.Application,
        *,
        user_id: UserID,
        wallet_id: WalletID,
    ) -> list[PaymentMethodGet]:
        return await _fake_list_wallet_payment_methods(app, user_id, wallet_id)

    async def _get(
        app: web.Application,
        *,
        payment_method_id: PaymentMethodID,
        user_id: UserID,
        wallet_id: WalletID,
    ) -> PaymentMethodGet:
        return await _fake_get_wallet_payment_method(
            app, user_id, wallet_id, payment_method_id
        )

    async def _del(
        app: web.Application,
        *,
        payment_method_id: PaymentMethodID,
        user_id: UserID,
        wallet_id: WalletID,
    ) -> None:
        await _fake_delete_wallet_payment_method(
            app, user_id, wallet_id, payment_method_id
        )

    async def _pay(
        app: web.Application,
        *,
        payment_method_id: PaymentMethodID,
        amount_dollars: Decimal,
        target_credits: Decimal,
        product_name: str,
        wallet_id: WalletID,
        wallet_name: str,
        user_id: UserID,
        user_name: str,
        user_email: EmailStr,
        user_address: UserInvoiceAddress,
        stripe_price_id: StripePriceID,
        stripe_tax_rate_id: StripeTaxRateID,
        comment: str | None = None,
    ) -> PaymentTransaction:

        assert await _get(
            app,
            payment_method_id=payment_method_id,
            user_id=user_id,
            wallet_id=wallet_id,
        )

        return await _fake_pay_with_payment_method(
            app,
            amount_dollars,
            target_credits,
            product_name,
            wallet_id,
            wallet_name,
            user_id,
            user_name,
            user_email,
            payment_method_id,
            comment,
        )

    async def _get_invoice_url(
        app: web.Application,
        *,
        payment_method_id: PaymentMethodID,
        user_id: UserID,
        wallet_id: WalletID,
    ) -> HttpUrl:
        return await _fake_get_payment_invoice_url(
            app, user_id, wallet_id, payment_method_id
        )

    return {
        "init_payment": mocker.patch(
            "simcore_service_webserver.payments._onetime_api._rpc.init_payment",
            autospec=True,
            side_effect=_init,
        ),
        "cancel_payment": mocker.patch(
            "simcore_service_webserver.payments._onetime_api._rpc.cancel_payment",
            autospec=True,
            side_effect=_cancel,
        ),
        "get_payments_page": mocker.patch(
            "simcore_service_webserver.payments._onetime_api._rpc.get_payments_page",
            autospec=True,
            side_effect=_get_page,
        ),
        "init_creation_of_payment_method": mocker.patch(
            "simcore_service_webserver.payments._methods_api._rpc.init_creation_of_payment_method",
            autospec=True,
            side_effect=_init_pm,
        ),
        "cancel_creation_of_payment_method": mocker.patch(
            "simcore_service_webserver.payments._methods_api._rpc.cancel_creation_of_payment_method",
            autospec=True,
            side_effect=_cancel_pm,
        ),
        "list_payment_methods": mocker.patch(
            "simcore_service_webserver.payments._methods_api._rpc.list_payment_methods",
            autospec=True,
            side_effect=_list_pm,
        ),
        "get_payment_method": mocker.patch(
            "simcore_service_webserver.payments._methods_api._rpc.get_payment_method",
            autospec=True,
            side_effect=_get,
        ),
        "delete_payment_method": mocker.patch(
            "simcore_service_webserver.payments._methods_api._rpc.delete_payment_method",
            autospec=True,
            side_effect=_del,
        ),
        "pay_with_payment_method": mocker.patch(
            "simcore_service_webserver.payments._onetime_api._rpc.pay_with_payment_method",
            autospec=True,
            side_effect=_pay,
        ),
        "get_payment_invoice_url": mocker.patch(
            "simcore_service_webserver.payments._onetime_api._rpc.get_payment_invoice_url",
            autospec=True,
            side_effect=_get_invoice_url,
        ),
    }


@pytest.fixture
def setup_user_pre_registration_details_db(
    postgres_db: sa.engine.Engine, logged_user: UserInfoDict, faker: Faker
) -> Iterator[int]:
    with postgres_db.connect() as con:
        result = con.execute(
            users_pre_registration_details.insert()
            .values(
                user_id=logged_user["id"],
                pre_email=faker.email(),
                pre_first_name=faker.first_name(),
                pre_last_name=faker.last_name(),
                pre_phone=faker.phone_number(),
                institution=faker.company(),
                address=faker.address().replace("\n", ", "),
                city=faker.city(),
                state=faker.state(),
                country=faker.random_element([c.name for c in pycountry.countries]),
                postal_code=faker.postcode(),
                created_by=None,
            )
            .returning(sa.literal_column("*"))
        )
        row = result.fetchone()
        assert row
        yield cast(int, row[0])
        con.execute(users_pre_registration_details.delete())

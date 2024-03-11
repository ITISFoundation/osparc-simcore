# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=not-an-iterable


from collections.abc import Callable, Iterator
from typing import NamedTuple

import httpx
import pytest
import respx
from faker import Faker
from fastapi import FastAPI, status
from fastapi.encoders import jsonable_encoder
from models_library.api_schemas_webserver.wallets import PaymentMethodID
from models_library.payments import UserInvoiceAddress
from pydantic import ValidationError, parse_obj_as
from pytest_simcore.helpers.rawdata_fakers import random_payment_method_view
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.utils_envs import setenvs_from_dict
from respx import MockRouter
from simcore_service_payments.core.settings import ApplicationSettings
from simcore_service_payments.models.payments_gateway import (
    BatchGetPaymentMethods,
    GetPaymentMethod,
    InitPayment,
    InitPaymentMethod,
    PaymentInitiated,
    PaymentMethodInitiated,
    PaymentMethodsBatch,
    StripeTaxExempt,
)
from simcore_service_payments.models.schemas.acknowledgements import (
    AckPaymentWithPaymentMethod,
)
from simcore_service_payments.services.payments_gateway import PaymentsGatewayApi


@pytest.fixture
def app_environment(
    monkeypatch: pytest.MonkeyPatch,
    app_environment: EnvVarsDict,
    with_disabled_rabbitmq_and_rpc: None,
    with_disabled_postgres: None,
):
    # set environs
    return setenvs_from_dict(
        monkeypatch,
        {**app_environment, "PAYMENTS_GATEWAY_TAX_FEATURE_ENABLED": False},
    )


#
# mock payments-gateway-service API
#


@pytest.fixture
def mock_payments_gateway_service_api_base(app: FastAPI) -> Iterator[MockRouter]:
    """
    If external_environment is present, then this mock is not really used
    and instead the test runs against some real services
    """
    settings: ApplicationSettings = app.state.settings

    with respx.mock(
        base_url=settings.PAYMENTS_GATEWAY_URL,
        assert_all_called=False,
        assert_all_mocked=True,  # IMPORTANT: KEEP always True!
    ) as respx_mock:
        yield respx_mock


@pytest.fixture
def mock_payments_routes(faker: Faker) -> Callable:
    def _mock(mock_router: MockRouter):
        def _init_200(request: httpx.Request):
            assert "*" not in request.headers["X-Init-Api-Secret"]
            _excluded_fields = {
                "user_address",
                "stripe_price_id",
                "stripe_tax_rate_id",
                "stripe_tax_exempt_value",
            }
            try:
                # This will raise a ValidationError because 'required_field' is not provided
                assert InitPayment.parse_raw(request.content) is not None
            except ValidationError as e:
                assert len(e.raw_errors) == 4
                for raw_error in e.raw_errors:
                    _excluded_fields.remove(raw_error._loc)
                assert bool(_excluded_fields) is False

            return httpx.Response(
                status.HTTP_200_OK,
                json=jsonable_encoder(PaymentInitiated(payment_id=faker.uuid4())),
            )

        def _cancel_200(request: httpx.Request):
            assert PaymentInitiated.parse_raw(request.content) is not None
            assert "*" not in request.headers["X-Init-Api-Secret"]

            # responds with an empty authough it can also contain a message
            return httpx.Response(status.HTTP_200_OK, json={})

        mock_router.post(
            path="/init",
            name="init_payment",
        ).mock(side_effect=_init_200)

        mock_router.post(
            path="/cancel",
            name="cancel_payment",
        ).mock(side_effect=_cancel_200)

    return _mock


@pytest.fixture
def no_funds_payment_method_id(faker: Faker) -> PaymentMethodID:
    """Fake Paymets-Gateway will decline payments with this payment-method id due to insufficient -funds

    USE create_fake_payment_method_in_db to inject this payment-method in DB
    Emulates https://stripe.com/docs/testing#declined-payments
    """
    return parse_obj_as(PaymentMethodID, "no_funds_payment_method_id")


@pytest.fixture
def mock_payments_methods_routes(
    faker: Faker, no_funds_payment_method_id: PaymentMethodID
) -> Iterator[Callable]:
    class PaymentMethodInfoTuple(NamedTuple):
        init: InitPaymentMethod
        get: GetPaymentMethod

    _payment_methods: dict[str, PaymentMethodInfoTuple] = {}

    def _mock(mock_router: MockRouter):
        def _init(request: httpx.Request):
            assert "*" not in request.headers["X-Init-Api-Secret"]

            pm_id = faker.uuid4()
            _payment_methods[pm_id] = PaymentMethodInfoTuple(
                init=InitPaymentMethod.parse_raw(request.content),
                get=GetPaymentMethod(**random_payment_method_view(id=pm_id)),
            )

            return httpx.Response(
                status.HTTP_200_OK,
                json=jsonable_encoder(PaymentMethodInitiated(payment_method_id=pm_id)),
            )

        def _get(request: httpx.Request, pm_id: PaymentMethodID):
            assert "*" not in request.headers["X-Init-Api-Secret"]

            try:
                _, payment_method = _payment_methods[pm_id]
                return httpx.Response(
                    status.HTTP_200_OK, json=jsonable_encoder(payment_method)
                )
            except KeyError:
                return httpx.Response(status.HTTP_404_NOT_FOUND)

        def _del(request: httpx.Request, pm_id: PaymentMethodID):
            assert "*" not in request.headers["X-Init-Api-Secret"]

            try:
                _payment_methods.pop(pm_id)
                return httpx.Response(status.HTTP_204_NO_CONTENT)
            except KeyError:
                return httpx.Response(status.HTTP_404_NOT_FOUND)

        def _batch_get(request: httpx.Request):
            assert "*" not in request.headers["X-Init-Api-Secret"]
            batch = BatchGetPaymentMethods.parse_raw(request.content)

            try:
                items = [_payment_methods[pm].get for pm in batch.payment_methods_ids]
            except KeyError:
                return httpx.Response(status.HTTP_404_NOT_FOUND)

            return httpx.Response(
                status.HTTP_200_OK,
                json=jsonable_encoder(PaymentMethodsBatch(items=items)),
            )

        def _pay(request: httpx.Request, pm_id: PaymentMethodID):
            assert "*" not in request.headers["X-Init-Api-Secret"]
            _excluded_fields = {
                "user_address",
                "stripe_price_id",
                "stripe_tax_rate_id",
                "stripe_tax_exempt_value",
            }
            try:
                # This will raise a ValidationError because 'required_field' is not provided
                assert InitPayment.parse_raw(request.content) is not None
            except ValidationError as e:
                assert len(e.raw_errors) == 4
                for raw_error in e.raw_errors:
                    _excluded_fields.remove(raw_error._loc)
                assert bool(_excluded_fields) is False

            # checks
            _get(request, pm_id)

            payment_id = faker.uuid4()

            if pm_id == no_funds_payment_method_id:
                # SEE https://stripe.com/docs/testing#declined-payments
                return httpx.Response(
                    status.HTTP_200_OK,
                    json=jsonable_encoder(
                        AckPaymentWithPaymentMethod(
                            success=False,
                            message=f"Insufficient Fonds '{pm_id}'",
                            invoice_url=None,
                            payment_id=payment_id,
                        )
                    ),
                )

            return httpx.Response(
                status.HTTP_200_OK,
                json=jsonable_encoder(
                    # NOTE: without
                    AckPaymentWithPaymentMethod(
                        success=True,
                        message=f"Payment '{payment_id}' with payment-method '{pm_id}'",
                        invoice_url=faker.url(),
                        provider_payment_id="pi_123456ABCDEFG123456ABCDE",
                        payment_id=payment_id,
                    )
                ),
            )

        # ------

        mock_router.post(
            path="/payment-methods:init",
            name="init_payment_method",
        ).mock(side_effect=_init)

        mock_router.post(
            path="/payment-methods:batchGet",
            name="batch_get_payment_methods",
        ).mock(side_effect=_batch_get)

        mock_router.get(
            path__regex=r"/payment-methods/(?P<pm_id>[\w-]+)$",
            name="get_payment_method",
        ).mock(side_effect=_get)

        mock_router.delete(
            path__regex=r"/payment-methods/(?P<pm_id>[\w-]+)$",
            name="delete_payment_method",
        ).mock(side_effect=_del)

        mock_router.post(
            path__regex=r"/payment-methods/(?P<pm_id>[\w-]+):pay$",
            name="pay_with_payment_method",
        ).mock(side_effect=_pay)

    yield _mock

    _payment_methods.clear()


@pytest.fixture
def mock_payments_gateway_service(
    mock_payments_gateway_service_api_base: MockRouter,
    mock_payments_routes: Callable,
    mock_payments_methods_routes: Callable,
) -> MockRouter:
    # Rests against mock payments-gateway
    mock_payments_routes(mock_payments_gateway_service_api_base)
    mock_payments_methods_routes(mock_payments_gateway_service_api_base)
    return mock_payments_gateway_service_api_base


@pytest.fixture(
    params=[
        10,
        999999.99609375,  # SEE https://github.com/ITISFoundation/appmotion-exchange/issues/2
    ],
)
def amount_dollars(request: pytest.FixtureRequest) -> float:
    return request.param


#
# These tests are testing backward compatibility with Payment Gateway without new tax feature changes
#


async def test_payment_methods_workflow_with_tax_feature_disabled(
    app: FastAPI,
    faker: Faker,
    mock_payments_gateway_service: MockRouter,
    amount_dollars: float,
):
    settings: ApplicationSettings = app.state.settings
    assert settings.PAYMENTS_GATEWAY_TAX_FEATURE_ENABLED is False

    payments_gateway_api: PaymentsGatewayApi = PaymentsGatewayApi.get_from_app_state(
        app
    )
    assert payments_gateway_api

    # init payment-method
    initiated = await payments_gateway_api.init_payment_method(
        InitPaymentMethod(
            user_name=faker.user_name(),
            user_email=faker.email(),
            wallet_name=faker.word(),
        )
    )
    # CRUD
    payment_method_id = initiated.payment_method_id

    payment_with_payment_method = await payments_gateway_api.pay_with_payment_method(
        id_=payment_method_id,
        payment=InitPayment(
            amount_dollars=amount_dollars,
            credits=faker.pydecimal(positive=True, right_digits=2, left_digits=4),  # type: ignore
            user_name=faker.user_name(),
            user_email=faker.email(),
            user_address=UserInvoiceAddress(country="CH"),
            wallet_name=faker.word(),
            stripe_price_id=faker.word(),
            stripe_tax_rate_id=faker.word(),
            stripe_tax_exempt_value=StripeTaxExempt.none,
        ),
        payment_gateway_tax_feature_enabled=settings.PAYMENTS_GATEWAY_TAX_FEATURE_ENABLED,
    )
    assert payment_with_payment_method.success


async def test_one_time_payment_workflow_with_tax_feature_disabled(
    app: FastAPI,
    faker: Faker,
    mock_payments_gateway_service_or_none: MockRouter | None,
    amount_dollars: float,
):
    settings: ApplicationSettings = app.state.settings
    assert settings.PAYMENTS_GATEWAY_TAX_FEATURE_ENABLED is False

    payment_gateway_api = PaymentsGatewayApi.get_from_app_state(app)
    assert payment_gateway_api

    # init
    payment_initiated = await payment_gateway_api.init_payment(
        payment=InitPayment(
            amount_dollars=amount_dollars,
            credits=faker.pydecimal(positive=True, right_digits=2, left_digits=4),  # type: ignore
            user_name=faker.user_name(),
            user_email=faker.email(),
            user_address=UserInvoiceAddress(country="CH"),
            wallet_name=faker.word(),
            stripe_price_id=faker.word(),
            stripe_tax_rate_id=faker.word(),
            stripe_tax_exempt_value=StripeTaxExempt.none,
        ),
        payment_gateway_tax_feature_enabled=settings.PAYMENTS_GATEWAY_TAX_FEATURE_ENABLED,
    )

    # form url
    submission_link = payment_gateway_api.get_form_payment_url(
        payment_initiated.payment_id
    )

    app_settings: ApplicationSettings = app.state.settings
    assert submission_link.host == app_settings.PAYMENTS_GATEWAY_URL.host

    # cancel
    payment_canceled = await payment_gateway_api.cancel_payment(payment_initiated)
    assert payment_canceled is not None

    # check mock
    if mock_payments_gateway_service_or_none:
        assert mock_payments_gateway_service_or_none.routes["init_payment"].called
        assert mock_payments_gateway_service_or_none.routes["cancel_payment"].called

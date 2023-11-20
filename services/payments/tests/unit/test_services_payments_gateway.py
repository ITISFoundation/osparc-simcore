# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


import httpx
import pytest
from faker import Faker
from fastapi import FastAPI, status
from pytest_simcore.helpers.utils_envs import EnvVarsDict, setenvs_from_dict
from respx import MockRouter
from simcore_service_payments.core.settings import ApplicationSettings
from simcore_service_payments.models.payments_gateway import (
    InitPayment,
    InitPaymentMethod,
)
from simcore_service_payments.services.payments_gateway import (
    PaymentsGatewayApi,
    PaymentsGatewayError,
    _raise_as_payments_gateway_error,
    setup_payments_gateway,
)


async def test_setup_payment_gateway_api(app_environment: EnvVarsDict):
    new_app = FastAPI()
    new_app.state.settings = ApplicationSettings.create_from_envs()
    with pytest.raises(AttributeError):
        PaymentsGatewayApi.get_from_app_state(new_app)

    setup_payments_gateway(new_app)
    payment_gateway_api = PaymentsGatewayApi.get_from_app_state(new_app)

    assert payment_gateway_api is not None


@pytest.fixture
def app_environment(
    monkeypatch: pytest.MonkeyPatch,
    app_environment: EnvVarsDict,
    with_disabled_rabbitmq_and_rpc: None,
    with_disabled_postgres: None,
    external_environment: EnvVarsDict,
):
    # set environs
    return setenvs_from_dict(
        monkeypatch,
        {**app_environment, **external_environment},
    )


async def test_payment_gateway_responsiveness(
    app: FastAPI,
    mock_payments_gateway_service_api_base: MockRouter,
):
    # NOTE: should be standard practice
    payment_gateway_api = PaymentsGatewayApi.get_from_app_state(app)
    assert payment_gateway_api

    mock_payments_gateway_service_api_base.get(
        path="/",
        name="healthcheck",
    ).respond(status.HTTP_503_SERVICE_UNAVAILABLE)

    assert await payment_gateway_api.ping()
    assert not await payment_gateway_api.is_healhy()

    mock_payments_gateway_service_api_base.get(
        path="/",
        name="healthcheck",
    ).respond(status.HTTP_200_OK)

    assert await payment_gateway_api.ping()
    assert await payment_gateway_api.is_healhy()


@pytest.fixture(
    params=[
        10,
        999999.99609375,  # SEE https://github.com/ITISFoundation/appmotion-exchange/issues/2
    ],
)
def amount_dollars(request: pytest.FixtureRequest) -> float:
    return request.param


@pytest.mark.acceptance_test(
    "https://github.com/ITISFoundation/osparc-simcore/pull/4715"
)
async def test_one_time_payment_workflow(
    app: FastAPI,
    faker: Faker,
    mock_payments_gateway_service_or_none: MockRouter | None,
    amount_dollars: float,
):
    payment_gateway_api = PaymentsGatewayApi.get_from_app_state(app)
    assert payment_gateway_api

    # init
    payment_initiated = await payment_gateway_api.init_payment(
        payment=InitPayment(
            amount_dollars=amount_dollars,
            credits=faker.pydecimal(positive=True, right_digits=2, left_digits=4),  # type: ignore
            user_name=faker.user_name(),
            user_email=faker.email(),
            wallet_name=faker.word(),
        )
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


@pytest.mark.can_run_against_external()
async def test_payment_methods_workflow(
    app: FastAPI,
    faker: Faker,
    mock_payments_gateway_service_or_none: MockRouter | None,
    amount_dollars: float,
):
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

    # from url
    form_link = payments_gateway_api.get_form_payment_method_url(
        initiated.payment_method_id
    )

    app_settings: ApplicationSettings = app.state.settings
    assert form_link.host == app_settings.PAYMENTS_GATEWAY_URL.host

    # CRUD
    payment_method_id = initiated.payment_method_id

    # get payment-method
    got_payment_method = await payments_gateway_api.get_payment_method(
        payment_method_id
    )
    assert got_payment_method.id == payment_method_id
    print(got_payment_method.json(indent=2))

    # list payment-methods
    items = await payments_gateway_api.get_many_payment_methods([payment_method_id])

    assert items
    assert len(items) == 1
    assert items[0] == got_payment_method

    payment_with_payment_method = await payments_gateway_api.pay_with_payment_method(
        id_=payment_method_id,
        payment=InitPayment(
            amount_dollars=amount_dollars,
            credits=faker.pydecimal(positive=True, right_digits=2, left_digits=4),  # type: ignore
            user_name=faker.user_name(),
            user_email=faker.email(),
            wallet_name=faker.word(),
        ),
    )
    assert payment_with_payment_method.success

    # delete payment-method
    await payments_gateway_api.delete_payment_method(payment_method_id)

    with pytest.raises(PaymentsGatewayError) as err_info:
        await payments_gateway_api.get_payment_method(payment_method_id)

    assert str(err_info.value)
    assert err_info.value.operation_id == "PaymentsGatewayApi.get_payment_method"

    http_status_error = err_info.value.http_status_error
    assert http_status_error.response.status_code == status.HTTP_404_NOT_FOUND

    if mock_payments_gateway_service_or_none:
        # all defined payment-methods
        for route in mock_payments_gateway_service_or_none.routes:
            if route.name and "payment_method" in route.name:
                assert route.called


async def test_payments_gateway_error_exception():
    async def _go():
        with _raise_as_payments_gateway_error(operation_id="foo"):
            async with httpx.AsyncClient(
                app=FastAPI(),
                base_url="http://payments.testserver.io",
            ) as client:
                response = await client.post("/foo", params={"x": "3"}, json={"y": 12})
                response.raise_for_status()

    with pytest.raises(PaymentsGatewayError) as err_info:
        await _go()
    err = err_info.value
    assert isinstance(err, PaymentsGatewayError)

    assert "curl -X POST" in err.get_detailed_message()

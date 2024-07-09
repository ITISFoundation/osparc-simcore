# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


import pytest
from fastapi import FastAPI, status
from models_library.payments import StripeInvoiceID
from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict, setenvs_from_dict
from respx import MockRouter
from simcore_service_payments.core.settings import ApplicationSettings
from simcore_service_payments.services.stripe import StripeApi, setup_stripe


async def test_setup_stripe_api(app_environment: EnvVarsDict):
    new_app = FastAPI()
    new_app.state.settings = ApplicationSettings.create_from_envs()
    with pytest.raises(AttributeError):
        StripeApi.get_from_app_state(new_app)

    setup_stripe(new_app)
    stripe_api = StripeApi.get_from_app_state(new_app)

    assert stripe_api is not None


@pytest.fixture
def app_environment(
    monkeypatch: pytest.MonkeyPatch,
    app_environment: EnvVarsDict,
    with_disabled_rabbitmq_and_rpc: None,
    with_disabled_postgres: None,
    external_stripe_environment: EnvVarsDict,
):
    # set environs
    return setenvs_from_dict(
        monkeypatch,
        {**app_environment, **external_stripe_environment},
    )


async def test_stripe_responsiveness(
    app: FastAPI,
    mock_payments_stripe_api_base: MockRouter,
):
    stripe_api: StripeApi = StripeApi.get_from_app_state(app)
    assert stripe_api

    mock_payments_stripe_api_base.get(
        path="/",
        name="ping healthcheck",
    ).respond(status.HTTP_503_SERVICE_UNAVAILABLE)
    mock_payments_stripe_api_base.get(
        path="/v1/products",
        name="healthy healthcheck",
    ).respond(status.HTTP_503_SERVICE_UNAVAILABLE)

    assert await stripe_api.ping()
    assert not await stripe_api.is_healthy()

    mock_payments_stripe_api_base.get(
        path="/",
        name="ping healthcheck",
    ).respond(status.HTTP_200_OK)
    mock_payments_stripe_api_base.get(
        path="/v1/products",
        name="healthy healthcheck",
    ).respond(status.HTTP_200_OK)

    assert await stripe_api.ping()
    assert await stripe_api.is_healthy()


async def test_get_invoice(
    app: FastAPI,
    mock_stripe_or_none: MockRouter | None,
    stripe_invoice_id: StripeInvoiceID,
):
    stripe_api: StripeApi = StripeApi.get_from_app_state(app)
    assert stripe_api

    assert await stripe_api.is_healthy()

    _invoice = await stripe_api.get_invoice(
        stripe_invoice_id=StripeInvoiceID(stripe_invoice_id)
    )
    assert _invoice
    assert _invoice.hosted_invoice_url

    if mock_stripe_or_none:
        assert mock_stripe_or_none.routes["list_products"].called
        assert mock_stripe_or_none.routes["get_invoice"].called

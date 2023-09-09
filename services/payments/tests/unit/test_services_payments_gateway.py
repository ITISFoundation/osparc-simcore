# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


import pytest
from faker import Faker
from fastapi import FastAPI
from simcore_service_payments.core.settings import ApplicationSettings
from simcore_service_payments.models.payments_gateway import InitPayment
from simcore_service_payments.services.payments_gateway import (
    get_form_payment_url,
    init_payment,
)


def mock_payments_gateway_service_api():
    # respx fake interface
    ...


@pytest.mark.xfail(reason="UNDER DEV")
async def test_one_time_payment_workflow(app: FastAPI, faker: Faker):
    app_settings: ApplicationSettings = app.state.settings

    payment = InitPayment(
        amount_dollars=100,
        credits=100,
        user_name=faker.username(),
        user_email=faker.email(),
        wallet_name=faker.word(),
    )

    payment_initiated = await init_payment(payment, auth=None)

    submission_link = get_form_payment_url(payment_initiated.payment_id)
    assert submission_link.host == app_settings.PAYMENTS_GATEWAY_URL.host

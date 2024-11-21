# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from collections.abc import AsyncIterator

import httpx
import pytest
from faker import Faker
from fastapi import FastAPI, status
from fastapi.encoders import jsonable_encoder
from models_library.api_schemas_payments.errors import (
    PaymentMethodNotFoundError,
    PaymentNotFoundError,
)
from pytest_mock import MockerFixture
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_service_payments.models.schemas.acknowledgements import (
    AckPayment,
    AckPaymentMethod,
)
from simcore_service_payments.models.schemas.errors import DefaultApiError

pytest_simcore_core_services_selection = [
    "postgres",
]

pytest_simcore_ops_services_selection = [
    "adminer",
]


@pytest.fixture
def app_environment(
    app_environment: EnvVarsDict,
    postgres_env_vars_dict: EnvVarsDict,
    external_envfile_dict: EnvVarsDict,
    wait_for_postgres_ready_and_db_migrated: None,
    monkeypatch: pytest.MonkeyPatch,
) -> EnvVarsDict:
    # set environs
    monkeypatch.delenv("PAYMENTS_POSTGRES", raising=False)

    return setenvs_from_dict(
        monkeypatch,
        {
            **app_environment,
            **postgres_env_vars_dict,
            **external_envfile_dict,
            "POSTGRES_CLIENT_NAME": "payments-service-pg-client",
        },
    )


@pytest.fixture
def app(
    app: FastAPI,
    mocker: MockerFixture,
) -> FastAPI:
    app.state.notifier = mocker.MagicMock()
    return app


@pytest.fixture
async def client(
    client: httpx.AsyncClient, external_envfile_dict: EnvVarsDict
) -> AsyncIterator[httpx.AsyncClient]:
    # EITHER tests against external payments API
    if external_base_url := external_envfile_dict.get("PAYMENTS_SERVICE_API_BASE_URL"):
        # If there are external secrets, build a new client and point to `external_base_url`
        print(
            "🚨 EXTERNAL: tests running against external payment API at",
            external_base_url,
        )
        async with httpx.AsyncClient(
            app=None,
            base_url=external_base_url,
            headers={"Content-Type": "application/json"},
        ) as new_client:
            yield new_client
    # OR tests against app
    else:
        yield client


async def test_payments_api_authentication(
    with_disabled_rabbitmq_and_rpc: None,
    client: httpx.AsyncClient,
    faker: Faker,
    auth_headers: dict[str, str],
):
    payments_id = faker.uuid4()
    payment_ack = jsonable_encoder(
        AckPayment(success=True, invoice_url=faker.url()).model_dump()
    )

    # w/o header
    response = await client.post(
        f"/v1/payments/{payments_id}:ack",
        json=payment_ack,
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED, response.json()

    # w/ header
    response = await client.post(
        f"/v1/payments/{payments_id}:ack", json=payment_ack, headers=auth_headers
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND, response.json()
    error = DefaultApiError.model_validate(response.json())
    assert PaymentNotFoundError.msg_template.format(payment_id=payments_id) == str(
        error.detail
    )


async def test_payments_methods_api_authentication(
    with_disabled_rabbitmq_and_rpc: None,
    client: httpx.AsyncClient,
    faker: Faker,
    auth_headers: dict[str, str],
):
    payment_method_id = faker.uuid4()
    payment_method_ack = AckPaymentMethod(
        success=True, message=faker.word()
    ).model_dump()

    # w/o header
    response = await client.post(
        f"/v1/payments-methods/{payment_method_id}:ack",
        json=payment_method_ack,
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED, response.json()

    # same but w/ header
    response = await client.post(
        response.request.url.path,
        content=response.request.content,
        headers=auth_headers,
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND, response.json()
    error = DefaultApiError.model_validate(response.json())
    assert PaymentMethodNotFoundError.msg_template.format(
        payment_method_id=payment_method_id
    ) == str(error.detail)

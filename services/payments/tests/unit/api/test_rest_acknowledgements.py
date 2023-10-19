# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from collections.abc import AsyncIterator

import httpx
import pytest
from faker import Faker
from fastapi import status
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.utils_envs import setenvs_from_dict
from simcore_service_payments.models.schemas.acknowledgements import AckPayment

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
    external_secret_envs: EnvVarsDict,
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
            **external_secret_envs,
            "POSTGRES_CLIENT_NAME": "payments-service-pg-client",
        },
    )


@pytest.fixture
async def client(
    client: httpx.AsyncClient, external_secret_envs: EnvVarsDict
) -> AsyncIterator[httpx.AsyncClient]:

    # tests against external payments API
    if external_base_url := external_secret_envs.get("PAYMENTS_SERVICE_API_BASE_URL"):
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

    # tests against app
    yield client


async def test_payments_api_authentication(
    with_disabled_rabbitmq_and_rpc: None,
    client: httpx.AsyncClient,
    faker: Faker,
    auth_headers: dict[str, str],
):
    payments_id = faker.uuid4()
    payment_ack = AckPayment(success=True, invoice_url=faker.url()).dict()

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

    print(response.json())

    # NOTE: for the moment this entry is not implemented
    assert response.status_code == status.HTTP_404_NOT_FOUND, response.json()

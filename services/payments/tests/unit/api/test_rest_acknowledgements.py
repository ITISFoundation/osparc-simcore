# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


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
    wait_for_postgres_ready_and_db_migrated: None,
    monkeypatch: pytest.MonkeyPatch,
):
    # set environs
    monkeypatch.delenv("PAYMENTS_POSTGRES", raising=False)

    return setenvs_from_dict(
        monkeypatch,
        {
            **app_environment,
            **postgres_env_vars_dict,
            "POSTGRES_CLIENT_NAME": "payments-service-pg-client",
        },
    )


async def test_payments_api_authentication(
    mock_patch_setup_rabbitmq_and_rpc: None,
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

    # NOTE: for the moment this entry is not implemented
    assert (
        response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    ), response.json()

    # TODO: test using schemathesis
    # TODO: test ack w/o init
    # TODO: test ack fail with saved?

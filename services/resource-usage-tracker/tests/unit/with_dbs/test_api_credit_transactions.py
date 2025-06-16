from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import httpx
import pytest
import sqlalchemy as sa
from faker import Faker
from models_library.api_schemas_resource_usage_tracker.credit_transactions import (
    CreditTransactionCreateBody,
    WalletTotalCredits,
)
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.resource_tracker import (
    CreditClassification,
    CreditTransactionStatus,
    ServiceRunStatus,
)
from servicelib.rabbitmq import RabbitMQClient, RabbitMQRPCClient
from servicelib.rabbitmq.rpc_interfaces.resource_usage_tracker import (
    credit_transactions,
    service_runs,
)
from servicelib.rabbitmq.rpc_interfaces.resource_usage_tracker.errors import (
    WalletTransactionError,
)
from simcore_postgres_database.models.resource_tracker_credit_transactions import (
    resource_tracker_credit_transactions,
)
from simcore_postgres_database.models.resource_tracker_service_runs import (
    resource_tracker_service_runs,
)
from simcore_service_resource_usage_tracker.services.modules.db import (
    credit_transactions_db,
)
from simcore_service_resource_usage_tracker.services.service_runs import ServiceRunPage
from starlette import status
from yarl import URL

pytest_simcore_core_services_selection = [
    "postgres",
    "rabbit",
]
pytest_simcore_ops_services_selection = [
    "adminer",
]


@pytest.fixture()
def resource_tracker_credit_transactions_db(
    postgres_db: sa.engine.Engine,
) -> Iterator[None]:
    with postgres_db.connect() as con:

        yield

        con.execute(resource_tracker_credit_transactions.delete())


_WALLET_ID = 1


async def test_credit_transactions_workflow(
    create_rabbitmq_client: Callable[[str], RabbitMQClient],
    mocked_redis_server: None,
    postgres_db: sa.engine.Engine,
    async_client: httpx.AsyncClient,
    resource_tracker_credit_transactions_db: None,
    rpc_client: RabbitMQRPCClient,
    faker: Faker,
):
    url = URL("/v1/credit-transactions")

    response = await async_client.post(
        url=f"{url}",
        json={
            "product_name": "osparc",
            "wallet_id": _WALLET_ID,
            "wallet_name": "string",
            "user_id": 1,
            "user_email": "string",
            "osparc_credits": 1234.54,
            "payment_transaction_id": "string",
            "created_at": "2023-08-31T13:04:23.941Z",
        },
    )
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["credit_transaction_id"] == 1

    response = await async_client.post(
        url=f"{url}",
        json={
            "product_name": "osparc",
            "wallet_id": _WALLET_ID,
            "wallet_name": "string",
            "user_id": 1,
            "user_email": "string",
            "osparc_credits": 105.5,
            "payment_transaction_id": "string",
            "created_at": "2023-08-31T13:04:23.941Z",
        },
    )
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["credit_transaction_id"] == 2

    response = await async_client.post(
        url=f"{url}",
        json={
            "product_name": "osparc",
            "wallet_id": 2,
            "wallet_name": "string",
            "user_id": 1,
            "user_email": "string",
            "osparc_credits": 10.85,
            "payment_transaction_id": "string",
            "created_at": "2023-08-31T13:04:23.941Z",
        },
    )
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["credit_transaction_id"] == 3

    url = URL("/v1/credit-transactions/credits:sum")
    response = await async_client.post(
        f'{url.with_query({"product_name": "osparc", "wallet_id": 1})}'
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["wallet_id"] == _WALLET_ID
    _expected_credits = Decimal("1340.04")
    assert data["available_osparc_credits"] == float(_expected_credits)

    output = await credit_transactions.get_wallet_total_credits(
        rpc_client,
        product_name="osparc",
        wallet_id=_WALLET_ID,
    )
    assert output.available_osparc_credits == _expected_credits


_USER_ID_1 = 1
_USER_ID_2 = 2
_SERVICE_RUN_ID_1 = "1"
_SERVICE_RUN_ID_2 = "2"
_SERVICE_RUN_ID_3 = "3"
_SERVICE_RUN_ID_4 = "4"
_WALLET_ID_FOR_PAYING_DEBT__NOT_ENOUGH_CREDITS = 2
_WALLET_ID_FOR_PAYING_DEBT__ENOUGH_CREDITS = 3


@pytest.fixture()
def resource_tracker_setup_db(
    postgres_db: sa.engine.Engine,
    random_resource_tracker_service_run,
    random_resource_tracker_credit_transactions,
    project_id: ProjectID,
    product_name: ProductName,
    faker: Faker,
) -> Iterator[None]:
    with postgres_db.connect() as con:
        # Service run table
        result = con.execute(
            resource_tracker_service_runs.insert()
            .values(
                [
                    random_resource_tracker_service_run(
                        user_id=_USER_ID_1,
                        service_run_id=_SERVICE_RUN_ID_1,
                        product_name=product_name,
                        started_at=datetime.now(tz=UTC) - timedelta(hours=1),
                        stopped_at=datetime.now(tz=UTC),
                        project_id=project_id,
                        service_run_status=ServiceRunStatus.SUCCESS,
                        wallet_id=_WALLET_ID,
                    ),
                    random_resource_tracker_service_run(
                        user_id=_USER_ID_2,  # <-- different user
                        service_run_id=_SERVICE_RUN_ID_2,
                        product_name=product_name,
                        started_at=datetime.now(tz=UTC) - timedelta(hours=1),
                        stopped_at=None,
                        project_id=project_id,
                        service_run_status=ServiceRunStatus.RUNNING,  # <-- Runnin status
                        wallet_id=_WALLET_ID,
                    ),
                    random_resource_tracker_service_run(
                        user_id=_USER_ID_1,
                        service_run_id=_SERVICE_RUN_ID_3,
                        product_name=product_name,
                        started_at=datetime.now(tz=UTC) - timedelta(hours=1),
                        stopped_at=datetime.now(tz=UTC),
                        project_id=project_id,
                        service_run_status=ServiceRunStatus.SUCCESS,
                        wallet_id=_WALLET_ID,
                    ),
                    random_resource_tracker_service_run(
                        user_id=_USER_ID_1,
                        service_run_id=_SERVICE_RUN_ID_4,
                        product_name=product_name,
                        started_at=datetime.now(tz=UTC) - timedelta(hours=1),
                        stopped_at=datetime.now(tz=UTC),
                        project_id=faker.uuid4(),  # <-- different project
                        service_run_status=ServiceRunStatus.SUCCESS,
                        wallet_id=_WALLET_ID,
                    ),
                ]
            )
            .returning(resource_tracker_service_runs)
        )
        row = result.first()
        assert row

        # Transaction table
        result = con.execute(
            resource_tracker_credit_transactions.insert()
            .values(
                [
                    random_resource_tracker_credit_transactions(
                        user_id=_USER_ID_1,
                        service_run_id=_SERVICE_RUN_ID_1,
                        product_name=product_name,
                        payment_transaction_id=None,
                        osparc_credits=-50,
                        transaction_status=CreditTransactionStatus.BILLED,
                        transaction_classification=CreditClassification.DEDUCT_SERVICE_RUN,
                        wallet_id=_WALLET_ID,
                    ),
                    random_resource_tracker_credit_transactions(
                        user_id=_USER_ID_2,  # <-- different user
                        service_run_id=_SERVICE_RUN_ID_2,
                        product_name=product_name,
                        payment_transaction_id=None,
                        osparc_credits=-70,
                        transaction_status=CreditTransactionStatus.PENDING,  # <-- Pending status
                        transaction_classification=CreditClassification.DEDUCT_SERVICE_RUN,
                        wallet_id=_WALLET_ID,
                    ),
                    random_resource_tracker_credit_transactions(
                        user_id=_USER_ID_1,
                        osparc_credits=-100,
                        service_run_id=_SERVICE_RUN_ID_3,
                        product_name=product_name,
                        payment_transaction_id=None,
                        transaction_status=CreditTransactionStatus.IN_DEBT,  # <-- IN DEBT
                        transaction_classification=CreditClassification.DEDUCT_SERVICE_RUN,
                        wallet_id=_WALLET_ID,
                    ),
                    random_resource_tracker_credit_transactions(
                        user_id=_USER_ID_1,
                        osparc_credits=-90,
                        service_run_id=_SERVICE_RUN_ID_4,
                        product_name=product_name,
                        payment_transaction_id=None,
                        transaction_status=CreditTransactionStatus.BILLED,
                        transaction_classification=CreditClassification.DEDUCT_SERVICE_RUN,
                        wallet_id=_WALLET_ID,
                    ),
                    # We will add 2 more wallets for paying a debt test
                    random_resource_tracker_credit_transactions(
                        user_id=_USER_ID_1,
                        osparc_credits=50,  # <-- Not enough credits to pay the DEBT of -100
                        service_run_id=None,
                        product_name=product_name,
                        payment_transaction_id="INVITATION",
                        transaction_status=CreditTransactionStatus.BILLED,
                        transaction_classification=CreditClassification.ADD_WALLET_TOP_UP,
                        wallet_id=_WALLET_ID_FOR_PAYING_DEBT__NOT_ENOUGH_CREDITS,
                    ),
                    random_resource_tracker_credit_transactions(
                        user_id=_USER_ID_1,
                        osparc_credits=500,  # <-- Enough credits to pay the DEBT of -100
                        service_run_id=None,
                        product_name=product_name,
                        transaction_status=CreditTransactionStatus.BILLED,
                        transaction_classification=CreditClassification.ADD_WALLET_TOP_UP,
                        wallet_id=_WALLET_ID_FOR_PAYING_DEBT__ENOUGH_CREDITS,
                    ),
                ]
            )
            .returning(resource_tracker_credit_transactions)
        )
        row = result.first()
        assert row

        yield

        con.execute(resource_tracker_credit_transactions.delete())
        con.execute(resource_tracker_service_runs.delete())


async def test_get_project_wallet_total_credits(
    mocked_redis_server: None,
    resource_tracker_setup_db: None,
    rpc_client: RabbitMQRPCClient,
    project_id: ProjectID,
    product_name: ProductName,
):
    output = await credit_transactions.get_project_wallet_total_credits(
        rpc_client,
        product_name=product_name,
        wallet_id=_WALLET_ID,
        project_id=project_id,
    )
    assert isinstance(output, WalletTotalCredits)
    assert output.available_osparc_credits == -220

    output = await credit_transactions.get_project_wallet_total_credits(
        rpc_client,
        product_name=product_name,
        wallet_id=_WALLET_ID,
        project_id=project_id,
        transaction_status=CreditTransactionStatus.IN_DEBT,
    )
    assert isinstance(output, WalletTotalCredits)
    assert output.available_osparc_credits == -100


async def test_pay_project_debt(
    mocked_redis_server: None,
    resource_tracker_setup_db: None,
    rpc_client: RabbitMQRPCClient,
    project_id: ProjectID,
    product_name: ProductName,
    faker: Faker,
):
    total_wallet_credits_for_wallet_in_debt_in_beginning = (
        await credit_transactions.get_wallet_total_credits(
            rpc_client,
            product_name=product_name,
            wallet_id=_WALLET_ID,
        )
    )

    output = await credit_transactions.get_project_wallet_total_credits(
        rpc_client,
        product_name=product_name,
        wallet_id=_WALLET_ID,
        project_id=project_id,
        transaction_status=CreditTransactionStatus.IN_DEBT,
    )
    assert isinstance(output, WalletTotalCredits)
    assert output.available_osparc_credits == -100
    _project_debt_amount = output.available_osparc_credits

    # We test situation when new and current wallet transaction amount are not setup properly by the client (ex. webserver)
    new_wallet_transaction = CreditTransactionCreateBody(
        product_name=product_name,
        wallet_id=_WALLET_ID_FOR_PAYING_DEBT__NOT_ENOUGH_CREDITS,
        wallet_name="new wallet",
        user_id=_USER_ID_1,
        user_email=faker.email(),
        osparc_credits=_project_debt_amount - 50,  # <-- Negative number
        payment_transaction_id=f"Payment transaction from wallet {_WALLET_ID} to wallet {_WALLET_ID_FOR_PAYING_DEBT__NOT_ENOUGH_CREDITS}",
        created_at=datetime.now(UTC),
    )
    current_wallet_transaction = CreditTransactionCreateBody(
        product_name=product_name,
        wallet_id=_WALLET_ID,
        wallet_name="current wallet",
        user_id=_USER_ID_1,
        user_email=faker.email(),
        osparc_credits=-_project_debt_amount,  # <-- Positive number
        payment_transaction_id=f"Payment transaction from wallet {_WALLET_ID_FOR_PAYING_DEBT__NOT_ENOUGH_CREDITS} to wallet {_WALLET_ID}",
        created_at=datetime.now(UTC),
    )

    with pytest.raises(WalletTransactionError):
        await credit_transactions.pay_project_debt(
            rpc_client,
            project_id=project_id,
            current_wallet_transaction=current_wallet_transaction,
            new_wallet_transaction=new_wallet_transaction,
        )

    # We test situation when the new wallet doesn't have enough credits to pay the debt
    new_wallet_transaction = CreditTransactionCreateBody(
        product_name=product_name,
        wallet_id=_WALLET_ID_FOR_PAYING_DEBT__NOT_ENOUGH_CREDITS,
        wallet_name="new wallet",
        user_id=_USER_ID_1,
        user_email="test@test.com",
        osparc_credits=_project_debt_amount,  # <-- Negative number
        payment_transaction_id=f"Payment transaction from wallet {_WALLET_ID} to wallet {_WALLET_ID_FOR_PAYING_DEBT__NOT_ENOUGH_CREDITS}",
        created_at=datetime.now(UTC),
    )
    current_wallet_transaction = CreditTransactionCreateBody(
        product_name=product_name,
        wallet_id=_WALLET_ID,
        wallet_name="current wallet",
        user_id=_USER_ID_1,
        user_email="test@test.com",
        osparc_credits=-_project_debt_amount,  # <-- Positive number
        payment_transaction_id=f"Payment transaction from wallet {_WALLET_ID_FOR_PAYING_DEBT__NOT_ENOUGH_CREDITS} to wallet {_WALLET_ID}",
        created_at=datetime.now(UTC),
    )

    with pytest.raises(WalletTransactionError):
        await credit_transactions.pay_project_debt(
            rpc_client,
            project_id=project_id,
            current_wallet_transaction=current_wallet_transaction,
            new_wallet_transaction=new_wallet_transaction,
        )

    # We test the proper situation, when new wallet pays the debt of the project
    new_wallet_transaction = CreditTransactionCreateBody(
        product_name=product_name,
        wallet_id=_WALLET_ID_FOR_PAYING_DEBT__ENOUGH_CREDITS,
        wallet_name="new wallet",
        user_id=_USER_ID_1,
        user_email="test@test.com",
        osparc_credits=_project_debt_amount,  # <-- Negative number
        payment_transaction_id=f"Payment transaction from wallet {_WALLET_ID} to wallet {_WALLET_ID_FOR_PAYING_DEBT__ENOUGH_CREDITS}",
        created_at=datetime.now(UTC),
    )
    current_wallet_transaction = CreditTransactionCreateBody(
        product_name=product_name,
        wallet_id=_WALLET_ID,
        wallet_name="current wallet",
        user_id=_USER_ID_1,
        user_email="test@test.com",
        osparc_credits=-_project_debt_amount,  # <-- Positive number
        payment_transaction_id=f"Payment transaction from wallet {_WALLET_ID_FOR_PAYING_DEBT__ENOUGH_CREDITS} to wallet {_WALLET_ID}",
        created_at=datetime.now(UTC),
    )

    await credit_transactions.pay_project_debt(
        rpc_client,
        project_id=project_id,
        current_wallet_transaction=current_wallet_transaction,
        new_wallet_transaction=new_wallet_transaction,
    )

    # We additionaly check that the project is not in the DEBT anymore
    output = await credit_transactions.get_project_wallet_total_credits(
        rpc_client,
        product_name=product_name,
        wallet_id=_WALLET_ID,
        project_id=project_id,
        transaction_status=CreditTransactionStatus.IN_DEBT,
    )
    assert isinstance(output, WalletTotalCredits)
    assert output.available_osparc_credits == 0

    # We check whether the credits were deducted from the new wallet
    output = await credit_transactions.get_wallet_total_credits(
        rpc_client,
        product_name=product_name,
        wallet_id=_WALLET_ID_FOR_PAYING_DEBT__ENOUGH_CREDITS,
    )
    assert isinstance(output, WalletTotalCredits)
    assert (
        output.available_osparc_credits
        == 400  # <-- 100 was deduced from the new wallet
    )

    # We check whether the credits were added back to the original wallet
    output = await credit_transactions.get_wallet_total_credits(
        rpc_client,
        product_name=product_name,
        wallet_id=_WALLET_ID,
    )
    assert isinstance(output, WalletTotalCredits)
    assert (
        output.available_osparc_credits
        == total_wallet_credits_for_wallet_in_debt_in_beginning.available_osparc_credits
        + 100  # <-- 100 was added to the original wallet
    )


async def test_list_service_runs_with_transaction_status_filter(
    mocked_redis_server: None,
    resource_tracker_setup_db: None,
    rpc_client: RabbitMQRPCClient,
    project_id: ProjectID,
    product_name: ProductName,
):
    result = await service_runs.get_service_run_page(
        rpc_client,
        user_id=_USER_ID_1,
        product_name=product_name,
        wallet_id=_WALLET_ID,
        access_all_wallet_usage=True,
        project_id=project_id,
        transaction_status=CreditTransactionStatus.PENDING,
        offset=0,
        limit=1,
    )
    assert isinstance(result, ServiceRunPage)
    assert len(result.items) == 1
    assert result.total == 1

    result = await service_runs.get_service_run_page(
        rpc_client,
        user_id=_USER_ID_1,
        product_name=product_name,
        wallet_id=_WALLET_ID,
        access_all_wallet_usage=True,
        project_id=project_id,
        transaction_status=CreditTransactionStatus.IN_DEBT,
        offset=0,
        limit=1,
    )
    assert isinstance(result, ServiceRunPage)
    assert len(result.items) == 1
    assert result.total == 1

    result = await service_runs.get_service_run_page(
        rpc_client,
        user_id=_USER_ID_1,
        product_name=product_name,
        wallet_id=_WALLET_ID,
        access_all_wallet_usage=True,
        project_id=project_id,
        transaction_status=CreditTransactionStatus.BILLED,
        offset=0,
        limit=1,
    )
    assert isinstance(result, ServiceRunPage)
    assert len(result.items) == 1
    assert result.total == 1


async def test_sum_wallet_credits_db(
    mocked_redis_server: None,
    resource_tracker_setup_db: None,
    rpc_client: RabbitMQRPCClient,
    product_name: ProductName,
    initialized_app,
):
    engine = initialized_app.state.engine
    output_including_pending_transaction = (
        await credit_transactions_db.sum_wallet_credits(
            engine, product_name=product_name, wallet_id=_WALLET_ID
        )
    )
    assert output_including_pending_transaction.available_osparc_credits == Decimal(
        "-310.00"
    )
    output_excluding_pending_transaction = (
        await credit_transactions_db.sum_wallet_credits(
            engine,
            product_name=product_name,
            wallet_id=_WALLET_ID,
            include_pending_transactions=False,
        )
    )
    assert output_excluding_pending_transaction.available_osparc_credits == Decimal(
        "-240.00"
    )

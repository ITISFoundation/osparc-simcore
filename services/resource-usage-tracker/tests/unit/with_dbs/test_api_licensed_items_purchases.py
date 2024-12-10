# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=too-many-arguments

from datetime import UTC, datetime
from decimal import Decimal

#     # Remove the environment variable
#     if "RESOURCE_USAGE_TRACKER_S3" in os.environ:
#         monkeypatch.delenv("RESOURCE_USAGE_TRACKER_S3")
import sqlalchemy as sa
from models_library.api_schemas_resource_usage_tracker.licensed_items_purchases import (
    LicensedItemPurchaseGet,
    LicensedItemsPurchasesPage,
)
from models_library.resource_tracker_licensed_items_purchases import (
    LicensedItemsPurchasesCreate,
)
from servicelib.rabbitmq import RabbitMQRPCClient
from servicelib.rabbitmq.rpc_interfaces.resource_usage_tracker import (
    licensed_items_purchases,
)

pytest_simcore_core_services_selection = [
    "postgres",
    "rabbit",
]
pytest_simcore_ops_services_selection = [
    "adminer",
]


_USER_ID = 1


# @pytest.fixture
# async def mocked_export(mocker: MockerFixture) -> AsyncMock:
#     return mocker.patch(
#         "simcore_service_resource_usage_tracker.services.service_runs.service_runs_db.export_service_runs_table_to_s3",
#         autospec=True,
#     )


# @pytest.fixture
# async def mocked_presigned_link(mocker: MockerFixture) -> AsyncMock:
#     return mocker.patch(
#         "simcore_service_resource_usage_tracker.services.service_runs.SimcoreS3API.create_single_presigned_download_link",
#         return_value=TypeAdapter(AnyUrl).validate_python("https://www.testing.com/"),
#     )


# @pytest.fixture
# async def enable_resource_usage_tracker_s3(
#     mock_env: EnvVarsDict,
#     mocked_aws_server: ThreadedMotoServer,
#     mocked_s3_server_envs: EnvVarsDict,
#     mocked_s3_server_settings: S3Settings,
#     s3_client: S3Client,
#     monkeypatch: pytest.MonkeyPatch,
# ) -> None:
#     # Create bucket
#     await s3_client.create_bucket(Bucket=mocked_s3_server_settings.S3_BUCKET_NAME)


async def test_rpc_licensed_items_purchases_workflow(
    # enable_resource_usage_tracker_s3: None,
    mocked_redis_server: None,
    postgres_db: sa.engine.Engine,
    rpc_client: RabbitMQRPCClient,
    # mocked_export: Mock,
    # mocked_presigned_link: Mock,
):
    result = await licensed_items_purchases.get_licensed_items_purchases_page(
        rpc_client, product_name="osparc", wallet_id=1
    )
    assert isinstance(result, LicensedItemsPurchasesPage)  # nosec
    assert result.items == []
    assert result.total == 0

    _create_data = LicensedItemsPurchasesCreate(
        product_name="osparc",
        licensed_item_id="beb16d18-d57d-44aa-a638-9727fa4a72ef",
        wallet_id=1,
        wallet_name="My Wallet",
        pricing_unit_cost_id=1,
        pricing_unit_cost=Decimal(10),
        start_at=datetime.now(tz=UTC),
        expire_at=datetime.now(tz=UTC),
        num_of_seats=1,
        purchased_by_user=1,
        purchased_at=datetime.now(tz=UTC),
    )

    created_item = await licensed_items_purchases.create_licensed_item_purchase(
        rpc_client, data=_create_data
    )
    assert isinstance(result, LicensedItemPurchaseGet)  # nosec

    result = await licensed_items_purchases.get_licensed_item_purchase(
        rpc_client,
        product_name="osparc",
        licensed_item_purchase_id=created_item.licensed_item_purchase_id,
    )
    assert isinstance(result, LicensedItemPurchaseGet)  # nosec
    assert result.licensed_item_purchase_id == created_item.licensed_item_purchase_id

    result = await licensed_items_purchases.get_licensed_items_purchases_page(
        rpc_client, product_name="osparc", wallet_id=_create_data.wallet_id
    )
    assert isinstance(result, LicensedItemsPurchasesPage)  # nosec
    assert len(result.items) == 1
    assert result.total == 1

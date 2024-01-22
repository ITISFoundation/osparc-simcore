from datetime import datetime, timezone
from uuid import uuid4

from aws_library.s3.client import SimcoreS3API
from models_library.api_schemas_resource_usage_tracker.service_runs import (
    ServiceRunGet,
    ServiceRunPage,
)
from models_library.api_schemas_storage import S3BucketName
from models_library.products import ProductName
from models_library.resource_tracker import ServiceResourceUsagesFilters
from models_library.rest_ordering import OrderBy
from models_library.users import UserID
from models_library.wallets import WalletID
from pydantic import AnyUrl, PositiveInt
from servicelib.rabbitmq.rpc_interfaces.resource_usage_tracker.errors import (
    CustomResourceUsageTrackerError,
)

from ..models.resource_tracker_service_runs import ServiceRunWithCreditsDB
from ..modules.db.repositories.resource_tracker import ResourceTrackerRepository


async def list_service_runs(
    user_id: UserID,
    product_name: ProductName,
    resource_tracker_repo: ResourceTrackerRepository,
    limit: int = 20,
    offset: int = 0,
    wallet_id: WalletID | None = None,
    access_all_wallet_usage: bool = False,
    order_by: OrderBy | None = None,  # noqa: ARG001
    filters: ServiceResourceUsagesFilters | None = None,  # noqa: ARG001
) -> ServiceRunPage:
    started_from = None
    started_until = None
    if filters:
        started_from = filters.started_at.from_
        started_until = filters.started_at.until

    # Situation when we want to see all usage of a specific user
    if wallet_id is None and access_all_wallet_usage is False:
        total_service_runs: PositiveInt = await resource_tracker_repo.total_service_runs_by_product_and_user_and_wallet(
            product_name,
            user_id=user_id,
            wallet_id=None,
            started_from=started_from,
            started_until=started_until,
        )
        service_runs_db_model: list[
            ServiceRunWithCreditsDB
        ] = await resource_tracker_repo.list_service_runs_by_product_and_user_and_wallet(
            product_name,
            user_id=user_id,
            wallet_id=None,
            offset=offset,
            limit=limit,
            started_from=started_from,
            started_until=started_until,
            order_by=order_by,
        )
    # Situation when accountant user can see all users usage of the wallet
    elif wallet_id and access_all_wallet_usage is True:
        total_service_runs: PositiveInt = await resource_tracker_repo.total_service_runs_by_product_and_user_and_wallet(  # type: ignore[no-redef]
            product_name,
            user_id=None,
            wallet_id=wallet_id,
            started_from=started_from,
            started_until=started_until,
        )
        service_runs_db_model: list[  # type: ignore[no-redef]
            ServiceRunWithCreditsDB
        ] = await resource_tracker_repo.list_service_runs_by_product_and_user_and_wallet(
            product_name,
            user_id=None,
            wallet_id=wallet_id,
            offset=offset,
            limit=limit,
            started_from=started_from,
            started_until=started_until,
            order_by=order_by,
        )
    # Situation when regular user can see only his usage of the wallet
    elif wallet_id and access_all_wallet_usage is False:
        total_service_runs: PositiveInt = await resource_tracker_repo.total_service_runs_by_product_and_user_and_wallet(  # type: ignore[no-redef]
            product_name,
            user_id=user_id,
            wallet_id=wallet_id,
            started_from=started_from,
            started_until=started_until,
        )
        service_runs_db_model: list[  # type: ignore[no-redef]
            ServiceRunWithCreditsDB
        ] = await resource_tracker_repo.list_service_runs_by_product_and_user_and_wallet(
            product_name,
            user_id=user_id,
            wallet_id=wallet_id,
            offset=offset,
            limit=limit,
            started_from=started_from,
            started_until=started_until,
            order_by=order_by,
        )
    else:
        msg = "wallet_id and access_all_wallet_usage parameters must be specified together"
        raise CustomResourceUsageTrackerError(msg=msg)

    service_runs_api_model: list[ServiceRunGet] = []
    for service in service_runs_db_model:
        service_runs_api_model.append(
            ServiceRunGet.construct(
                service_run_id=service.service_run_id,
                wallet_id=service.wallet_id,
                wallet_name=service.wallet_name,
                user_id=service.user_id,
                project_id=service.project_id,
                project_name=service.project_name,
                node_id=service.node_id,
                node_name=service.node_name,
                service_key=service.service_key,
                service_version=service.service_version,
                service_type=service.service_type,
                service_resources=service.service_resources,
                started_at=service.started_at,
                stopped_at=service.stopped_at,
                service_run_status=service.service_run_status,
                credit_cost=service.osparc_credits,
                transaction_status=service.transaction_status,
            )
        )

    return ServiceRunPage(service_runs_api_model, total_service_runs)


async def export_service_runs(
    s3_client: SimcoreS3API,
    user_id: UserID,
    product_name: ProductName,
    resource_tracker_repo: ResourceTrackerRepository,
    wallet_id: WalletID | None = None,
    access_all_wallet_usage: bool = False,
    order_by: OrderBy | None = None,  # noqa: ARG001
    filters: ServiceResourceUsagesFilters | None = None,  # noqa: ARG001
) -> AnyUrl:
    started_from = None
    started_until = None
    if filters:
        started_from = filters.started_at.from_
        started_until = filters.started_at.until

    # Create S3 key name
    s3_bucket_name = S3BucketName("matus-testing")  # MD: parametrize bucket name
    file_name = f"{datetime.now(tz=timezone.utc).date()}__{uuid4()}.csv"
    s3_object_key = f"resource-usage-tracker-service-runs/{file_name}"

    # Export CSV to S3
    await resource_tracker_repo.export_service_runs_table_to_s3(
        product_name=product_name,
        s3_key=s3_object_key,
        user_id=user_id if access_all_wallet_usage is False else None,
        wallet_id=wallet_id,
        started_from=started_from,
        started_until=started_until,
        order_by=order_by,
    )

    # Create presigned S3 link
    generated_url: AnyUrl = await s3_client.create_presigned_link(
        bucket_name=s3_bucket_name, object_key=s3_object_key, expiration_secs=7200
    )
    return generated_url

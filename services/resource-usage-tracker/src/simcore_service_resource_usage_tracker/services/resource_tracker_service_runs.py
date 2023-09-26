from typing import Annotated

from fastapi import Depends, Query
from models_library.api_schemas_webserver.resource_usage import ServiceRunGet
from models_library.products import ProductName
from models_library.users import UserID
from models_library.wallets import WalletID
from pydantic import PositiveInt

from ..api.dependencies import get_repository
from ..models.pagination import LimitOffsetParamsWithDefault
from ..models.resource_tracker_service_run import ServiceRunDB, ServiceRunPage
from ..modules.db.repositories.resource_tracker import ResourceTrackerRepository


async def list_service_runs(
    user_id: UserID,
    product_name: ProductName,
    page_params: Annotated[LimitOffsetParamsWithDefault, Depends()],
    resource_tacker_repo: Annotated[
        ResourceTrackerRepository, Depends(get_repository(ResourceTrackerRepository))
    ],
    wallet_id: WalletID = Query(None),
    access_all_wallet_usage: bool = Query(None),
) -> ServiceRunPage:
    # Situation when we want to see all usage of a specific user
    if wallet_id is None and access_all_wallet_usage is None:
        total_service_runs: PositiveInt = (
            await resource_tacker_repo.total_service_runs_by_user_and_product(
                user_id, product_name
            )
        )
        service_runs_db_model: list[
            ServiceRunDB
        ] = await resource_tacker_repo.list_service_runs_by_user_and_product(
            user_id, product_name, page_params.offset, page_params.limit
        )
    # Situation when accountant user can see all users usage of the wallet
    elif wallet_id and access_all_wallet_usage is True:
        total_service_runs: PositiveInt = (  # type: ignore[no-redef]
            await resource_tacker_repo.total_service_runs_by_product_and_wallet(
                product_name, wallet_id
            )
        )
        service_runs_db_model: list[  # type: ignore[no-redef]
            ServiceRunDB
        ] = await resource_tacker_repo.list_service_runs_by_product_and_wallet(
            product_name, wallet_id, page_params.offset, page_params.limit
        )
    # Situation when regular user can see only his usage of the wallet
    elif wallet_id and access_all_wallet_usage is False:
        total_service_runs: PositiveInt = await resource_tacker_repo.total_service_runs_by_user_and_product_and_wallet(  # type: ignore[no-redef]
            user_id, product_name, wallet_id
        )
        service_runs_db_model: list[  # type: ignore[no-redef]
            ServiceRunDB
        ] = await resource_tacker_repo.list_service_runs_by_user_and_product_and_wallet(
            user_id, product_name, wallet_id, page_params.offset, page_params.limit
        )
    else:
        msg = "wallet_id and access_all_wallet_usage parameters must be specified together"
        raise ValueError(msg)

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
            )
        )

    return ServiceRunPage(service_runs_api_model, total_service_runs)

# pylint: disable=too-many-arguments
from fastapi import FastAPI
from models_library.api_schemas_directorv2.comp_runs import (
    ComputationRunRpcGetPage,
    ComputationTaskRpcGetPage,
)
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.rest_ordering import OrderBy
from models_library.users import UserID
from servicelib.rabbitmq import RPCRouter

from ...modules.db.repositories.comp_runs import CompRunsRepository
from ...modules.db.repositories.comp_tasks import CompTasksRepository
from ..dependencies.database import get_repository_instance

router = RPCRouter()


@router.expose(reraise_if_error_type=())
async def list_computations_latest_iteration_page(
    app: FastAPI,
    *,
    product_name: ProductName,
    user_id: UserID,
    # pagination
    offset: int = 0,
    limit: int = 20,
    # ordering
    order_by: OrderBy | None = None,
) -> ComputationRunRpcGetPage:
    comp_runs_repo = get_repository_instance(app, CompRunsRepository)
    total, comp_runs = await comp_runs_repo.list_for_user__only_latest_iterations(
        product_name=product_name,
        user_id=user_id,
        offset=offset,
        limit=limit,
        order_by=order_by,
    )
    return ComputationRunRpcGetPage(
        items=comp_runs,
        total=total,
    )


@router.expose(reraise_if_error_type=())
async def list_computations_latest_iteration_tasks_page(
    app: FastAPI,
    *,
    product_name: ProductName,
    user_id: UserID,
    project_id: ProjectID,
    # pagination
    offset: int = 0,
    limit: int = 20,
    # ordering
    order_by: OrderBy | None = None,
) -> ComputationTaskRpcGetPage:
    assert product_name  # nosec  NOTE: Whether project_id belong to the product_name was checked in the webserver
    assert user_id  # nosec  NOTE: Whether user_id has access to the project was checked in the webserver

    comp_tasks_repo = get_repository_instance(app, CompTasksRepository)
    total, comp_runs = (
        await comp_tasks_repo.list_computational_tasks_for_frontend_client(
            project_id=project_id,
            offset=offset,
            limit=limit,
            order_by=order_by,
        )
    )
    return ComputationTaskRpcGetPage(
        items=comp_runs,
        total=total,
    )

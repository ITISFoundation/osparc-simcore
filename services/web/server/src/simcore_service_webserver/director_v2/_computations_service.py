from aiohttp import web
from models_library.api_schemas_directorv2.comp_runs import (
    ComputationRunRpcGetPage,
    ComputationTaskRpcGetPage,
)
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.rest_ordering import OrderBy
from models_library.users import UserID
from pydantic import NonNegativeInt
from servicelib.rabbitmq.rpc_interfaces.director_v2 import computations

from ..projects.api import check_user_project_permission
from ..rabbitmq import get_rabbitmq_rpc_client


async def list_computations_latest_iteration(
    app: web.Application,
    product_name: ProductName,
    user_id: UserID,
    # pagination
    offset: int,
    limit: NonNegativeInt,
    # ordering
    order_by: OrderBy,
) -> ComputationRunRpcGetPage:
    """Returns the list of computations (only latest iterations)"""
    rpc_client = get_rabbitmq_rpc_client(app)
    return await computations.list_computations_latest_iteration_page(
        rpc_client,
        product_name=product_name,
        user_id=user_id,
        offset=offset,
        limit=limit,
        order_by=order_by,
    )


async def list_computations_latest_iteration_tasks(
    app: web.Application,
    product_name: ProductName,
    user_id: UserID,
    project_id: ProjectID,
    # pagination
    offset: int,
    limit: NonNegativeInt,
    # ordering
    order_by: OrderBy,
) -> ComputationTaskRpcGetPage:
    """Returns the list of tasks for the latest iteration of a computation"""

    await check_user_project_permission(
        app, project_id=project_id, user_id=user_id, product_name=product_name
    )

    rpc_client = get_rabbitmq_rpc_client(app)
    return await computations.list_computations_latest_iteration_tasks_page(
        rpc_client,
        product_name=product_name,
        user_id=user_id,
        project_id=project_id,
        offset=offset,
        limit=limit,
        order_by=order_by,
    )

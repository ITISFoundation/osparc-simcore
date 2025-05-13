from decimal import Decimal

from aiohttp import web
from models_library.computations import (
    ComputationRunWithAttributes,
    ComputationTaskWithAttributes,
)
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.rest_ordering import OrderBy
from models_library.users import UserID
from pydantic import NonNegativeInt
from servicelib.rabbitmq.rpc_interfaces.director_v2 import computations
from servicelib.rabbitmq.rpc_interfaces.resource_usage_tracker import (
    credit_transactions,
)
from servicelib.utils import limited_gather

from ..products.products_service import is_product_billable
from ..projects.api import (
    batch_get_project_name,
    check_user_project_permission,
    get_project_dict_legacy,
)
from ..projects.projects_metadata_service import (
    get_project_custom_metadata_or_empty_dict,
)
from ..rabbitmq import get_rabbitmq_rpc_client


async def list_computations_latest_iteration(
    app: web.Application,
    product_name: ProductName,
    user_id: UserID,
    # filters
    filter_only_running: bool,  # noqa: FBT001
    # pagination
    offset: int,
    limit: NonNegativeInt,
    # ordering
    order_by: OrderBy,
) -> tuple[int, list[ComputationRunWithAttributes]]:
    """Returns the list of computations (only latest iterations)"""
    rpc_client = get_rabbitmq_rpc_client(app)
    _runs_get = await computations.list_computations_latest_iteration_page(
        rpc_client,
        product_name=product_name,
        user_id=user_id,
        filter_only_running=filter_only_running,
        offset=offset,
        limit=limit,
        order_by=order_by,
    )

    # Get projects metadata (NOTE: MD: can be improved with a single batch call)
    _projects_metadata = await limited_gather(
        *[
            get_project_custom_metadata_or_empty_dict(
                app, project_uuid=item.project_uuid
            )
            for item in _runs_get.items
        ],
        limit=20,
    )

    # Get Root project names
    _projects_root_uuids: list[ProjectID] = []
    for item in _runs_get.items:
        if (
            prj_root_id := item.info.get("project_metadata", {}).get(
                "root_parent_project_id", None
            )
        ) is not None:
            _projects_root_uuids.append(ProjectID(prj_root_id))
        else:
            _projects_root_uuids.append(item.project_uuid)

    _projects_root_names = await batch_get_project_name(
        app, projects_uuids=_projects_root_uuids
    )

    _computational_runs_output = [
        ComputationRunWithAttributes(
            project_uuid=item.project_uuid,
            iteration=item.iteration,
            state=item.state,
            info=item.info,
            submitted_at=item.submitted_at,
            started_at=item.started_at,
            ended_at=item.ended_at,
            root_project_name=project_name,
            project_custom_metadata=project_metadata,
        )
        for item, project_metadata, project_name in zip(
            _runs_get.items, _projects_metadata, _projects_root_names, strict=True
        )
    ]

    return _runs_get.total, _computational_runs_output


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
) -> tuple[int, list[ComputationTaskWithAttributes]]:
    """Returns the list of tasks for the latest iteration of a computation"""

    await check_user_project_permission(
        app, project_id=project_id, user_id=user_id, product_name=product_name
    )

    rpc_client = get_rabbitmq_rpc_client(app)
    _tasks_get = await computations.list_computations_latest_iteration_tasks_page(
        rpc_client,
        product_name=product_name,
        user_id=user_id,
        project_id=project_id,
        offset=offset,
        limit=limit,
        order_by=order_by,
    )

    # Get node names (for all project nodes)
    project_dict = await get_project_dict_legacy(app, project_uuid=project_id)
    workbench = project_dict["workbench"]

    _service_run_ids = [item.service_run_id for item in _tasks_get.items]
    _is_product_billable = await is_product_billable(app, product_name=product_name)
    _service_run_osparc_credits: list[Decimal | None]
    if _is_product_billable:
        # NOTE: MD: can be improved with a single batch call
        _service_run_osparc_credits = await limited_gather(
            *[
                credit_transactions.get_transaction_current_credits_by_service_run_id(
                    rpc_client, service_run_id=_run_id
                )
                for _run_id in _service_run_ids
            ],
            limit=20,
        )
    else:
        _service_run_osparc_credits = [None for _ in _service_run_ids]

    # Final output
    _tasks_get_output = [
        ComputationTaskWithAttributes(
            project_uuid=item.project_uuid,
            node_id=item.node_id,
            state=item.state,
            progress=item.progress,
            image=item.image,
            started_at=item.started_at,
            ended_at=item.ended_at,
            log_download_link=item.log_download_link,
            node_name=workbench[f"{item.node_id}"].get("label", ""),
            osparc_credits=credits_or_none,
        )
        for item, credits_or_none in zip(
            _tasks_get.items, _service_run_osparc_credits, strict=True
        )
    ]
    return _tasks_get.total, _tasks_get_output

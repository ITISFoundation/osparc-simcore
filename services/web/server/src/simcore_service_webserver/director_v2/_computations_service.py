from decimal import Decimal

from aiohttp import web
from models_library.api_schemas_directorv2.comp_runs import (
    ComputationCollectionRunRpcGet,
    ComputationRunRpcGet,
)
from models_library.computations import (
    CollectionRunID,
    ComputationCollectionRunTaskWithAttributes,
    ComputationCollectionRunWithAttributes,
    ComputationRunWithAttributes,
    ComputationTaskWithAttributes,
)
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.projects_nodes import Node
from models_library.projects_nodes_io import NodeID
from models_library.rest_ordering import OrderBy
from models_library.services_types import ServiceRunID
from models_library.users import UserID
from pydantic import NonNegativeInt
from servicelib.rabbitmq import (
    RabbitMQRPCClient,
)
from servicelib.rabbitmq.rpc_interfaces.director_v2 import computations
from servicelib.rabbitmq.rpc_interfaces.resource_usage_tracker import (
    credit_transactions,
)
from servicelib.rabbitmq.rpc_interfaces.resource_usage_tracker.errors import (
    CreditTransactionNotFoundError,
)
from servicelib.utils import limited_gather

from ..products.products_service import is_product_billable
from ..projects._projects_nodes_repository import (
    get_by_projects,
)
from ..projects.api import (
    batch_get_project_name,
    check_user_project_permission,
)
from ..projects.projects_metadata_service import (
    get_project_custom_metadata_or_empty_dict,
    get_project_uuids_by_root_parent_project_id,
)
from ..rabbitmq import get_rabbitmq_rpc_client
from ._comp_runs_collections_service import get_comp_run_collection_or_none_by_id


async def _get_projects_metadata(
    app: web.Application,
    project_uuids: list[ProjectID],
) -> list[dict]:
    """Batch fetch project metadata with concurrency control"""
    # NOTE: MD: can be improved with a single batch call
    return await limited_gather(
        *[
            get_project_custom_metadata_or_empty_dict(app, project_uuid=uuid)
            for uuid in project_uuids
        ],
        limit=20,
    )


async def _get_root_project_names(
    app: web.Application, items: list[ComputationRunRpcGet]
) -> list[str]:
    """Resolve root project names from computation items"""
    root_uuids: list[ProjectID] = []
    for item in items:
        if root_id := item.info.get("project_metadata", {}).get(
            "root_parent_project_id"
        ):
            root_uuids.append(ProjectID(root_id))
        else:
            root_uuids.append(item.project_uuid)

    return await batch_get_project_name(app, projects_uuids=root_uuids)


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

    # Get projects metadata
    _projects_metadata = await _get_projects_metadata(
        app, project_uuids=[item.project_uuid for item in _runs_get.items]
    )
    # Get Root project names
    _projects_root_names = await _get_root_project_names(app, _runs_get.items)

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


async def list_computation_iterations(
    app: web.Application,
    *,
    product_name: ProductName,
    user_id: UserID,
    project_id: ProjectID,
    # filters
    include_children: bool = False,
    # pagination
    offset: int,
    limit: NonNegativeInt,
    # ordering
    order_by: OrderBy,
) -> tuple[int, list[ComputationRunWithAttributes]]:
    """Returns the list of computations for a specific project (all iterations)"""
    await check_user_project_permission(
        app, project_id=project_id, user_id=user_id, product_name=product_name
    )

    if include_children:
        child_projects = await get_project_uuids_by_root_parent_project_id(
            app, root_parent_project_uuid=project_id
        )
        child_projects_with_root = [*child_projects, project_id]
    else:
        child_projects_with_root = [project_id]

    rpc_client = get_rabbitmq_rpc_client(app)
    _runs_get = await computations.list_computations_iterations_page(
        rpc_client,
        product_name=product_name,
        user_id=user_id,
        project_ids=child_projects_with_root,
        offset=offset,
        limit=limit,
        order_by=order_by,
    )

    # NOTE: MD: can be improved, many times we ask for the same project
    # Get projects metadata
    _projects_metadata = await _get_projects_metadata(
        app, project_uuids=[item.project_uuid for item in _runs_get.items]
    )
    # Get Root project names
    root_project_names = await batch_get_project_name(app, projects_uuids=[project_id])
    assert len(root_project_names) == 1

    _computational_runs_output = [
        ComputationRunWithAttributes(
            project_uuid=item.project_uuid,
            iteration=item.iteration,
            state=item.state,
            info=item.info,
            submitted_at=item.submitted_at,
            started_at=item.started_at,
            ended_at=item.ended_at,
            root_project_name=root_project_names[0],
            project_custom_metadata=project_metadata,
        )
        for item, project_metadata in zip(
            _runs_get.items, _projects_metadata, strict=True
        )
    ]

    return _runs_get.total, _computational_runs_output


async def _get_credits_or_zero_by_service_run_id(
    rpc_client: RabbitMQRPCClient, service_run_id: ServiceRunID
) -> Decimal:
    try:
        return (
            await credit_transactions.get_transaction_current_credits_by_service_run_id(
                rpc_client, service_run_id=service_run_id
            )
        )
    except CreditTransactionNotFoundError:
        return Decimal(0)


async def list_computations_latest_iteration_tasks(
    app: web.Application,
    *,
    product_name: ProductName,
    user_id: UserID,
    project_id: ProjectID,
    # filters
    include_children: bool = False,
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

    if include_children:
        child_projects = await get_project_uuids_by_root_parent_project_id(
            app, root_parent_project_uuid=project_id
        )
        child_projects_with_root = [*child_projects, project_id]
    else:
        child_projects_with_root = [project_id]

    rpc_client = get_rabbitmq_rpc_client(app)
    _tasks_get = await computations.list_computations_latest_iteration_tasks_page(
        rpc_client,
        product_name=product_name,
        user_id=user_id,
        project_ids=child_projects_with_root,
        offset=offset,
        limit=limit,
        order_by=order_by,
    )

    # Get unique set of all project_uuids from comp_tasks
    unique_project_uuids = {task.project_uuid for task in _tasks_get.items}
    # Fetch projects metadata concurrently
    _projects_nodes: dict[ProjectID, list[tuple[NodeID, Node]]] = await get_by_projects(
        app, project_ids=unique_project_uuids
    )

    # Build a dict: project_uuid -> workbench
    project_uuid_to_workbench: dict[ProjectID, dict[NodeID, Node]] = {
        project_uuid: dict(nodes) for project_uuid, nodes in _projects_nodes.items()
    }

    _service_run_ids = [item.service_run_id for item in _tasks_get.items]
    _is_product_billable = await is_product_billable(app, product_name=product_name)
    _service_run_osparc_credits: list[Decimal | None]
    if _is_product_billable:
        # NOTE: MD: can be improved with a single batch call
        _service_run_osparc_credits = await limited_gather(
            *[
                _get_credits_or_zero_by_service_run_id(
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
            node_name=project_uuid_to_workbench[item.project_uuid][item.node_id].label
            or "Unknown",
            osparc_credits=credits_or_none,
        )
        for item, credits_or_none in zip(
            _tasks_get.items, _service_run_osparc_credits, strict=True
        )
    ]
    return _tasks_get.total, _tasks_get_output


async def _get_root_project_names_v2(
    app: web.Application, items: list[ComputationCollectionRunRpcGet]
) -> list[str]:
    root_uuids: list[ProjectID] = []
    for item in items:
        if root_id := item.info.get("project_metadata", {}).get(
            "root_parent_project_id"
        ):
            root_uuids.append(ProjectID(root_id))
        else:
            assert len(item.project_ids) > 0  # nosec
            root_uuids.append(ProjectID(item.project_ids[0]))

    return await batch_get_project_name(app, projects_uuids=root_uuids)


async def list_computation_collection_runs(
    app: web.Application,
    *,
    product_name: ProductName,
    user_id: UserID,
    # filters
    filter_by_root_project_id: ProjectID | None = None,
    filter_only_running: bool = False,
    # pagination
    offset: int,
    limit: NonNegativeInt,
) -> tuple[int, list[ComputationCollectionRunWithAttributes]]:
    child_projects_with_root = None
    if filter_by_root_project_id:
        await check_user_project_permission(
            app,
            project_id=filter_by_root_project_id,
            user_id=user_id,
            product_name=product_name,
        )
        # NOTE: Can be improved with checking if the provided project is a root project
        child_projects = await get_project_uuids_by_root_parent_project_id(
            app, root_parent_project_uuid=filter_by_root_project_id
        )
        child_projects_with_root = [*child_projects, filter_by_root_project_id]

    rpc_client = get_rabbitmq_rpc_client(app)
    _runs_get = await computations.list_computation_collection_runs_page(
        rpc_client,
        product_name=product_name,
        user_id=user_id,
        project_ids=child_projects_with_root,
        filter_only_running=filter_only_running,
        offset=offset,
        limit=limit,
    )

    # NOTE: MD: can be improved with a single batch call
    _comp_runs_collections = await limited_gather(
        *[
            get_comp_run_collection_or_none_by_id(
                app, collection_run_id=_run.collection_run_id
            )
            for _run in _runs_get.items
        ],
        limit=20,
    )
    # Get Root project names
    _projects_root_names = await _get_root_project_names_v2(app, _runs_get.items)

    _computational_runs_output = [
        ComputationCollectionRunWithAttributes(
            collection_run_id=item.collection_run_id,
            project_ids=item.project_ids,
            state=item.state,
            info=item.info,
            submitted_at=item.submitted_at,
            started_at=item.started_at,
            ended_at=item.ended_at,
            name=(
                run_collection.client_or_system_generated_display_name
                if run_collection and run_collection.is_generated_by_system is False
                else project_root_name
            ),
        )
        for item, run_collection, project_root_name in zip(
            _runs_get.items, _comp_runs_collections, _projects_root_names, strict=True
        )
    ]

    return _runs_get.total, _computational_runs_output


async def list_computation_collection_run_tasks(
    app: web.Application,
    *,
    product_name: ProductName,
    user_id: UserID,
    collection_run_id: CollectionRunID,
    # pagination
    offset: int,
    limit: NonNegativeInt,
) -> tuple[int, list[ComputationCollectionRunTaskWithAttributes]]:
    rpc_client = get_rabbitmq_rpc_client(app)
    _tasks_get = await computations.list_computation_collection_run_tasks_page(
        rpc_client,
        product_name=product_name,
        user_id=user_id,
        collection_run_id=collection_run_id,
        offset=offset,
        limit=limit,
    )

    # Get unique set of all project_uuids from comp_tasks
    unique_project_uuids = {task.project_uuid for task in _tasks_get.items}

    _projects_nodes: dict[ProjectID, list[tuple[NodeID, Node]]] = await get_by_projects(
        app, project_ids=unique_project_uuids
    )

    # Build a dict: project_uuid -> workbench
    project_uuid_to_workbench: dict[ProjectID, dict[NodeID, Node]] = {
        project_uuid: dict(nodes) for project_uuid, nodes in _projects_nodes.items()
    }

    # Fetch projects metadata concurrently
    _projects_metadata = await _get_projects_metadata(
        app, project_uuids=[item.project_uuid for item in _tasks_get.items]
    )

    _service_run_ids = [item.service_run_id for item in _tasks_get.items]
    _is_product_billable = await is_product_billable(app, product_name=product_name)
    _service_run_osparc_credits: list[Decimal | None]
    if _is_product_billable:
        # NOTE: MD: can be improved with a single batch call
        _service_run_osparc_credits = await limited_gather(
            *[
                _get_credits_or_zero_by_service_run_id(
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
        ComputationCollectionRunTaskWithAttributes(
            project_uuid=item.project_uuid,
            node_id=item.node_id,
            state=item.state,
            progress=item.progress,
            image=item.image,
            started_at=item.started_at,
            ended_at=item.ended_at,
            log_download_link=item.log_download_link,
            name=(
                custom_metadata.get("job_name")
                or project_uuid_to_workbench[item.project_uuid][item.node_id].label
                or "Unknown"
            ),
            osparc_credits=credits_or_none,
        )
        for item, credits_or_none, custom_metadata in zip(
            _tasks_get.items,
            _service_run_osparc_credits,
            _projects_metadata,
            strict=True,
        )
    ]
    return _tasks_get.total, _tasks_get_output

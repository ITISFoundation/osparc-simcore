""" Interface to other subsystems

    - Data validation
    - Operations on projects
        - are NOT handlers, therefore do not return web.Response
        - return data and successful HTTP responses (or raise them)
        - upon failure raise errors that can be also HTTP reponses
"""

import asyncio
import collections
import contextlib
import datetime
import json
import logging
from collections import defaultdict
from collections.abc import Generator
from contextlib import suppress
from decimal import Decimal
from pprint import pformat
from typing import Any, Final
from uuid import UUID, uuid4

from aiohttp import web
from models_library.api_schemas_clusters_keeper.ec2_instances import EC2InstanceTypeGet
from models_library.api_schemas_directorv2.dynamic_services import (
    GetProjectInactivityResponse,
)
from models_library.api_schemas_dynamic_scheduler.dynamic_services import (
    DynamicServiceStart,
    DynamicServiceStop,
)
from models_library.api_schemas_webserver.projects import ProjectPatch
from models_library.api_schemas_webserver.projects_nodes import NodePatch
from models_library.basic_types import KeyIDStr
from models_library.errors import ErrorDict
from models_library.products import ProductName
from models_library.projects import Project, ProjectID, ProjectIDStr
from models_library.projects_access import Owner
from models_library.projects_nodes import Node
from models_library.projects_nodes_io import NodeID, NodeIDStr, PortLink
from models_library.projects_state import (
    ProjectLocked,
    ProjectRunningState,
    ProjectState,
    ProjectStatus,
    RunningState,
)
from models_library.resource_tracker import (
    HardwareInfo,
    PricingAndHardwareInfoTuple,
    PricingInfo,
)
from models_library.services import DynamicServiceKey, ServiceKey, ServiceVersion
from models_library.services_resources import (
    DEFAULT_SINGLE_SERVICE_NAME,
    ServiceResourcesDict,
    ServiceResourcesDictHelpers,
)
from models_library.socketio import SocketMessageDict
from models_library.users import GroupID, UserID
from models_library.utils.fastapi_encoders import jsonable_encoder
from models_library.utils.json_serialization import json_dumps
from models_library.wallets import ZERO_CREDITS, WalletID, WalletInfo
from pydantic import ByteSize, parse_obj_as
from servicelib.aiohttp.application_keys import APP_FIRE_AND_FORGET_TASKS_KEY
from servicelib.common_headers import (
    UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE,
    X_FORWARDED_PROTO,
    X_SIMCORE_USER_AGENT,
)
from servicelib.logging_utils import get_log_record_extra, log_context
from servicelib.rabbitmq import RemoteMethodNotRegisteredError, RPCServerError
from servicelib.rabbitmq.rpc_interfaces.catalog import services as catalog_rpc
from servicelib.rabbitmq.rpc_interfaces.clusters_keeper.ec2_instances import (
    get_instance_type_details,
)
from servicelib.rabbitmq.rpc_interfaces.dynamic_scheduler.errors import (
    ServiceWaitingForManualInterventionError,
    ServiceWasNotFoundError,
)
from servicelib.utils import fire_and_forget_task, logged_gather
from simcore_postgres_database.models.users import UserRole
from simcore_postgres_database.utils_projects_nodes import (
    ProjectNodeCreate,
    ProjectNodesNodeNotFoundError,
)
from simcore_postgres_database.webserver_models import ProjectType

from ..application_settings import get_application_settings
from ..catalog import client as catalog_client
from ..director_v2 import api as director_v2_api
from ..dynamic_scheduler import api as dynamic_scheduler_api
from ..products import api as products_api
from ..products.api import get_product_name
from ..rabbitmq import get_rabbitmq_rpc_client
from ..redis import get_redis_lock_manager_client_sdk
from ..resource_manager.user_sessions import (
    PROJECT_ID_KEY,
    UserSessionID,
    managed_resource,
)
from ..resource_usage import api as rut_api
from ..socketio.messages import (
    SOCKET_IO_NODE_UPDATED_EVENT,
    SOCKET_IO_PROJECT_UPDATED_EVENT,
    send_message_to_standard_group,
    send_message_to_user,
)
from ..storage import api as storage_api
from ..users.api import FullNameDict, get_user, get_user_fullname, get_user_role
from ..users.exceptions import UserNotFoundError
from ..users.preferences_api import (
    PreferredWalletIdFrontendUserPreference,
    UserDefaultWalletNotFoundError,
    get_frontend_user_preference,
)
from ..wallets import api as wallets_api
from ..wallets.errors import WalletNotEnoughCreditsError
from . import _crud_api_delete, _nodes_api
from ._nodes_utils import set_reservation_same_as_limit, validate_new_service_resources
from ._wallets_api import connect_wallet_to_project, get_project_wallet
from .db import APP_PROJECT_DBAPI, ProjectDBAPI
from .exceptions import (
    ClustersKeeperNotAvailableError,
    DefaultPricingUnitNotFoundError,
    InvalidEC2TypeInResourcesSpecsError,
    InvalidKeysInResourcesSpecsError,
    NodeNotFoundError,
    ProjectInvalidRightsError,
    ProjectLockError,
    ProjectNodeConnectionsMissingError,
    ProjectNodeOutputPortMissingValueError,
    ProjectNodeRequiredInputsNotSetError,
    ProjectOwnerNotFoundInTheProjectAccessRightsError,
    ProjectStartsTooManyDynamicNodesError,
    ProjectTooManyProjectOpenedError,
)
from .lock import get_project_locked_state, is_project_locked, lock_project
from .models import ProjectDict
from .settings import ProjectsSettings, get_plugin_settings
from .utils import extract_dns_without_default_port

log = logging.getLogger(__name__)

PROJECT_REDIS_LOCK_KEY: str = "project:{}"


def _is_node_dynamic(node_key: str) -> bool:
    return "/dynamic/" in node_key


#
# GET project -----------------------------------------------------
#


async def get_project_for_user(
    app: web.Application,
    project_uuid: str,
    user_id: UserID,
    *,
    include_state: bool | None = False,
    check_permissions: str = "read",
) -> ProjectDict:
    """Returns a VALID project accessible to user

    :raises ProjectNotFoundError: if no match found
    :
    :return: schema-compliant project data
    :rtype: Dict
    """
    db = ProjectDBAPI.get_from_app_context(app)

    project, project_type = await db.get_project(
        user_id,
        project_uuid,
        check_permissions=check_permissions,  # type: ignore[arg-type]
    )

    # adds state if it is not a template
    if include_state:
        project = await add_project_states_for_user(
            user_id, project, project_type is ProjectType.TEMPLATE, app
        )

    Project.parse_obj(project)  # NOTE: only validates
    return project


async def get_project_type(
    app: web.Application, project_uuid: ProjectID
) -> ProjectType:
    db: ProjectDBAPI = app[APP_PROJECT_DBAPI]
    assert db  # nosec
    return await db.get_project_type(project_uuid)


#
# UPDATE project -----------------------------------------------------
#


async def update_project_last_change_timestamp(
    app: web.Application, project_uuid: ProjectID
):
    db: ProjectDBAPI = app[APP_PROJECT_DBAPI]
    assert db  # nosec
    await db.update_project_last_change_timestamp(ProjectIDStr(f"{project_uuid}"))


async def patch_project(
    app: web.Application,
    *,
    user_id: UserID,
    project_uuid: ProjectID,
    project_patch: ProjectPatch,
    product_name: ProductName,
):
    _project_patch_exclude_unset: dict[str, Any] = jsonable_encoder(
        project_patch, exclude_unset=True, by_alias=False
    )
    db: ProjectDBAPI = app[APP_PROJECT_DBAPI]

    # 1. Get project
    project_db = await db.get_project_db(project_uuid=project_uuid)

    # 2. Check user permissions
    _user_project_access_rights = await db.get_project_access_rights_for_user(
        user_id, project_uuid
    )
    if not _user_project_access_rights.write:
        raise ProjectInvalidRightsError(user_id=user_id, project_uuid=project_uuid)

    # 3. If patching access rights
    if new_prj_access_rights := _project_patch_exclude_unset.get("access_rights"):
        # 3.1 Check if user is Owner and therefore can modify access rights
        if not _user_project_access_rights.delete:
            raise ProjectInvalidRightsError(user_id=user_id, project_uuid=project_uuid)
        # 3.2 Ensure the prj owner is always in the access rights
        _prj_required_permissions = {
            "read": True,
            "write": True,
            "delete": True,
        }
        user: dict = await get_user(app, project_db.prj_owner)
        _prj_owner_primary_group = f'{user["primary_gid"]}'
        if _prj_owner_primary_group not in new_prj_access_rights:
            raise ProjectOwnerNotFoundInTheProjectAccessRightsError
        if new_prj_access_rights[_prj_owner_primary_group] != _prj_required_permissions:
            raise ProjectOwnerNotFoundInTheProjectAccessRightsError

    # 4. Patch the project
    await db.patch_project(
        project_uuid=project_uuid,
        new_partial_project_data=_project_patch_exclude_unset,
    )

    # 5. Make calls to director-v2 to keep data in sync (ex. comp_tasks DB table)
    await director_v2_api.create_or_update_pipeline(
        app, user_id, project_uuid, product_name=product_name
    )


#
# DELETE project -----------------------------------------------------
#


async def submit_delete_project_task(
    app: web.Application,
    project_uuid: ProjectID,
    user_id: UserID,
    simcore_user_agent: str,
) -> asyncio.Task:
    """
    Marks a project as deleted and schedules a task to performe the entire removal workflow
    using user_id's permissions.

    If this task is already scheduled, it returns it otherwise it creates a new one.

    The returned task can be ignored to implement a fire&forget or
    followed up with add_done_callback.

    raises ProjectDeleteError
    raises ProjectInvalidRightsError
    raises ProjectNotFoundError
    """
    await _crud_api_delete.mark_project_as_deleted(app, project_uuid, user_id)

    # Ensures ONE delete task per (project,user) pair
    task = get_delete_project_task(project_uuid, user_id)
    if not task:
        task = _crud_api_delete.schedule_task(
            app,
            project_uuid,
            user_id,
            simcore_user_agent,
            remove_project_dynamic_services,
            log,
        )
    return task


def get_delete_project_task(
    project_uuid: ProjectID, user_id: UserID
) -> asyncio.Task | None:
    if tasks := _crud_api_delete.get_scheduled_tasks(project_uuid, user_id):
        assert len(tasks) == 1, f"{tasks=}"  # nosec
        return tasks[0]
    return None


#
# PROJECT NODES -----------------------------------------------------
#


async def _get_default_pricing_and_hardware_info(
    app: web.Application,
    product_name: str,
    service_key: str,
    service_version: str,
    project_uuid: ProjectID,
    node_uuid: NodeID,
) -> PricingAndHardwareInfoTuple:
    service_pricing_plan_get = await rut_api.get_default_service_pricing_plan(
        app,
        product_name=product_name,
        service_key=ServiceKey(service_key),
        service_version=ServiceVersion(service_version),
    )
    if service_pricing_plan_get.pricing_units:
        for unit in service_pricing_plan_get.pricing_units:
            if unit.default:
                return PricingAndHardwareInfoTuple(
                    service_pricing_plan_get.pricing_plan_id,
                    unit.pricing_unit_id,
                    unit.current_cost_per_unit_id,
                    unit.specific_info.aws_ec2_instances,
                )
    raise DefaultPricingUnitNotFoundError(
        project_uuid=f"{project_uuid}", node_uuid=f"{node_uuid}"
    )


_MACHINE_TOTAL_RAM_SAFE_MARGIN_RATIO: Final[
    float
] = 0.1  # NOTE: machines always have less available RAM than advertised
_SIDECARS_OPS_SAFE_RAM_MARGIN: Final[ByteSize] = parse_obj_as(ByteSize, "1GiB")
_CPUS_SAFE_MARGIN: Final[float] = 1.4
_MIN_NUM_CPUS: Final[float] = 0.5


async def update_project_node_resources_from_hardware_info(
    app: web.Application,
    *,
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
    service_key: ServiceKey,
    service_version: ServiceVersion,
    product_name: str,
    hardware_info: HardwareInfo,
) -> None:
    if not hardware_info.aws_ec2_instances:
        return
    try:
        rabbitmq_rpc_client = get_rabbitmq_rpc_client(app)
        unordered_list_ec2_instance_types: list[
            EC2InstanceTypeGet
        ] = await get_instance_type_details(
            rabbitmq_rpc_client,
            instance_type_names=set(hardware_info.aws_ec2_instances),
        )

        assert unordered_list_ec2_instance_types  # nosec

        # NOTE: with the current implementation, there is no use to get the instance past the first one
        def _by_type_name(ec2: EC2InstanceTypeGet) -> bool:
            return bool(ec2.name == hardware_info.aws_ec2_instances[0])

        selected_ec2_instance_type = next(
            iter(filter(_by_type_name, unordered_list_ec2_instance_types))
        )

        # now update the project node required resources
        # NOTE: we keep a safe margin with the RAM as the dask-sidecar "sees"
        # less memory than the machine theoretical amount
        node_resources = await get_project_node_resources(
            app, user_id, project_id, node_id, service_key, service_version
        )
        scalable_service_name = DEFAULT_SINGLE_SERVICE_NAME
        new_cpus_value = float(selected_ec2_instance_type.cpus) - _CPUS_SAFE_MARGIN
        new_ram_value = int(
            selected_ec2_instance_type.ram
            - _MACHINE_TOTAL_RAM_SAFE_MARGIN_RATIO * selected_ec2_instance_type.ram
            - _SIDECARS_OPS_SAFE_RAM_MARGIN
        )
        if DEFAULT_SINGLE_SERVICE_NAME not in node_resources:
            # NOTE: we go for the largest sub-service and scale it up/down
            scalable_service_name, hungry_service_resources = max(
                node_resources.items(),
                key=lambda service_to_resources: int(
                    service_to_resources[1].resources["RAM"].limit
                ),
            )
            log.debug(
                "the most hungry service is %s",
                f"{scalable_service_name=}:{hungry_service_resources}",
            )
            other_services_resources = collections.Counter({"RAM": 0, "CPUS": 0})
            for service_name, sub_service_resources in node_resources.items():
                if service_name != scalable_service_name:
                    other_services_resources.update(
                        {
                            "RAM": sub_service_resources.resources["RAM"].limit,
                            "CPU": sub_service_resources.resources["CPU"].limit,
                        }
                    )
            new_cpus_value = max(
                float(selected_ec2_instance_type.cpus)
                - _CPUS_SAFE_MARGIN
                - other_services_resources["CPU"],
                _MIN_NUM_CPUS,
            )
            new_ram_value = int(
                selected_ec2_instance_type.ram
                - _MACHINE_TOTAL_RAM_SAFE_MARGIN_RATIO * selected_ec2_instance_type.ram
                - other_services_resources["RAM"]
                - _SIDECARS_OPS_SAFE_RAM_MARGIN
            )
        # scale the service
        node_resources[scalable_service_name].resources["CPU"].set_value(new_cpus_value)
        node_resources[scalable_service_name].resources["RAM"].set_value(new_ram_value)
        db = ProjectDBAPI.get_from_app_context(app)
        await db.update_project_node(
            user_id,
            project_id,
            node_id,
            product_name,
            required_resources=ServiceResourcesDictHelpers.create_jsonable(
                node_resources
            ),
            check_update_allowed=False,
        )
    except StopIteration as exc:
        raise InvalidEC2TypeInResourcesSpecsError(
            ec2_types=set(hardware_info.aws_ec2_instances)
        ) from exc

    except KeyError as exc:
        raise InvalidKeysInResourcesSpecsError(missing_key=f"{exc}") from exc
    except (
        RemoteMethodNotRegisteredError,
        RPCServerError,
        asyncio.TimeoutError,
    ) as exc:
        raise ClustersKeeperNotAvailableError from exc


async def _check_project_node_has_all_required_inputs(
    db: ProjectDBAPI, user_id: UserID, project_uuid: ProjectID, node_id: NodeID
) -> None:

    project_dict, _ = await db.get_project(user_id, f"{project_uuid}")

    nodes_map: dict[NodeID, Node] = {
        NodeID(k): Node(**v) for k, v in project_dict["workbench"].items()
    }
    node = nodes_map[node_id]

    unset_required_inputs: list[str] = []
    unset_outputs_in_upstream: list[tuple[str, str]] = []

    def _check_required_input(required_input_key: KeyIDStr) -> None:
        input_entry = None
        if node.inputs:
            input_entry = node.inputs.get(required_input_key, None)
        if input_entry is None:
            # NOT linked to any node connect service or set value manually(whichever applies)
            unset_required_inputs.append(required_input_key)
            return

        assert isinstance(input_entry, PortLink)  # nosec
        source_node_id = input_entry.node_uuid
        source_output_key = input_entry.output

        source_node = nodes_map[source_node_id]

        output_entry = None
        if source_node.outputs:
            output_entry = source_node.outputs.get(source_output_key, None)
        if output_entry is None:
            unset_outputs_in_upstream.append((source_output_key, source_node.label))

    for required_input in node.inputs_required:
        _check_required_input(required_input)

    node_with_required_inputs = node.label
    if unset_required_inputs:
        raise ProjectNodeConnectionsMissingError(
            unset_required_inputs=unset_required_inputs,
            node_with_required_inputs=node_with_required_inputs,
        )

    if unset_outputs_in_upstream:
        raise ProjectNodeOutputPortMissingValueError(
            unset_outputs_in_upstream=unset_outputs_in_upstream
        )


async def _start_dynamic_service(
    request: web.Request,
    *,
    service_key: ServiceKey,
    service_version: ServiceVersion,
    product_name: str,
    user_id: UserID,
    project_uuid: ProjectID,
    node_uuid: NodeID,
    graceful_start: bool = False,
) -> None:
    if not _is_node_dynamic(service_key):
        return

    # this is a dynamic node, let's gather its resources and start it

    db: ProjectDBAPI = ProjectDBAPI.get_from_app_context(request.app)

    try:
        await _check_project_node_has_all_required_inputs(
            db, user_id, project_uuid, node_uuid
        )
    except ProjectNodeRequiredInputsNotSetError as e:
        if graceful_start:
            log.info(
                "Did not start '%s' because of missing required inputs: %s",
                node_uuid,
                e,
            )
            return
        raise

    save_state = False
    user_role: UserRole = await get_user_role(request.app, user_id)
    if user_role > UserRole.GUEST:
        save_state = await ProjectDBAPI.get_from_app_context(
            request.app
        ).has_permission(
            user_id=user_id, project_uuid=f"{project_uuid}", permission="write"
        )

    lock_key = _nodes_api.get_service_start_lock_key(user_id, project_uuid)
    redis_client_sdk = get_redis_lock_manager_client_sdk(request.app)
    project_settings: ProjectsSettings = get_plugin_settings(request.app)

    async with redis_client_sdk.lock_context(
        lock_key,
        blocking=True,
        blocking_timeout_s=_nodes_api.get_total_project_dynamic_nodes_creation_interval(
            project_settings.PROJECTS_MAX_NUM_RUNNING_DYNAMIC_NODES
        ),
    ):
        project_running_nodes = await director_v2_api.list_dynamic_services(
            request.app, user_id, f"{project_uuid}"
        )
        _nodes_api.check_num_service_per_projects_limit(
            app=request.app,
            number_of_services=len(project_running_nodes),
            user_id=user_id,
            project_uuid=project_uuid,
        )

        # Get wallet/pricing/hardware information
        wallet_info, pricing_info, hardware_info = None, None, None
        product = products_api.get_current_product(request)
        app_settings = get_application_settings(request.app)
        if (
            product.is_payment_enabled
            and app_settings.WEBSERVER_CREDIT_COMPUTATION_ENABLED
        ):
            # Deal with Wallet
            project_wallet = await get_project_wallet(
                request.app, project_id=project_uuid
            )
            if project_wallet is None:
                user_default_wallet_preference = await get_frontend_user_preference(
                    request.app,
                    user_id=user_id,
                    product_name=product_name,
                    preference_class=PreferredWalletIdFrontendUserPreference,
                )
                if user_default_wallet_preference is None:
                    raise UserDefaultWalletNotFoundError(uid=user_id)
                project_wallet_id = parse_obj_as(
                    WalletID, user_default_wallet_preference.value
                )
                await connect_wallet_to_project(
                    request.app,
                    product_name=product_name,
                    project_id=project_uuid,
                    user_id=user_id,
                    wallet_id=project_wallet_id,
                )
            else:
                project_wallet_id = project_wallet.wallet_id
            # Check whether user has access to the wallet
            wallet = (
                await wallets_api.get_wallet_with_available_credits_by_user_and_wallet(
                    request.app,
                    user_id=user_id,
                    wallet_id=project_wallet_id,
                    product_name=product_name,
                )
            )
            wallet_info = WalletInfo(
                wallet_id=project_wallet_id,
                wallet_name=wallet.name,
                wallet_credit_amount=wallet.available_credits,
            )

            # Deal with Pricing plan/unit
            output = await db.get_project_node_pricing_unit_id(
                project_uuid=project_uuid, node_uuid=node_uuid
            )
            if output:
                pricing_plan_id, pricing_unit_id = output
            else:
                (
                    pricing_plan_id,
                    pricing_unit_id,
                    _,
                    _,
                ) = await _get_default_pricing_and_hardware_info(
                    request.app,
                    product_name,
                    service_key,
                    service_version,
                    project_uuid,
                    node_uuid,
                )
                await db.connect_pricing_unit_to_project_node(
                    project_uuid,
                    node_uuid,
                    pricing_plan_id,
                    pricing_unit_id,
                )

            # Check for zero credits (if pricing unit is greater than 0).
            pricing_unit_get = await rut_api.get_pricing_plan_unit(
                request.app, product_name, pricing_plan_id, pricing_unit_id
            )
            pricing_unit_cost_id = pricing_unit_get.current_cost_per_unit_id
            aws_ec2_instances = pricing_unit_get.specific_info.aws_ec2_instances

            if (
                pricing_unit_get.current_cost_per_unit > Decimal(0)
                and wallet.available_credits <= ZERO_CREDITS
            ):
                raise WalletNotEnoughCreditsError(
                    reason=f"Wallet '{wallet.name}' has {wallet.available_credits} credits."
                )

            pricing_info = PricingInfo(
                pricing_plan_id=pricing_plan_id,
                pricing_unit_id=pricing_unit_id,
                pricing_unit_cost_id=pricing_unit_cost_id,
            )
            hardware_info = HardwareInfo(aws_ec2_instances=aws_ec2_instances)
            await update_project_node_resources_from_hardware_info(
                request.app,
                user_id=user_id,
                project_id=project_uuid,
                node_id=node_uuid,
                product_name=product_name,
                hardware_info=hardware_info,
                service_key=service_key,
                service_version=service_version,
            )

        service_resources: ServiceResourcesDict = await get_project_node_resources(
            request.app,
            user_id=user_id,
            project_id=project_uuid,
            node_id=node_uuid,
            service_key=service_key,
            service_version=service_version,
        )
        await dynamic_scheduler_api.run_dynamic_service(
            app=request.app,
            dynamic_service_start=DynamicServiceStart(
                product_name=product_name,
                can_save=save_state,
                project_id=project_uuid,
                user_id=user_id,
                service_key=DynamicServiceKey(service_key),
                service_version=service_version,
                service_uuid=node_uuid,
                request_dns=extract_dns_without_default_port(request.url),
                request_scheme=request.headers.get(
                    X_FORWARDED_PROTO, request.url.scheme
                ),
                simcore_user_agent=request.headers.get(
                    X_SIMCORE_USER_AGENT, UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE
                ),
                service_resources=service_resources,
                wallet_info=wallet_info,
                pricing_info=pricing_info,
                hardware_info=hardware_info,
            ),
        )


async def add_project_node(
    request: web.Request,
    project: dict[str, Any],
    user_id: UserID,
    product_name: str,
    service_key: ServiceKey,
    service_version: ServiceVersion,
    service_id: str | None,
) -> NodeID:
    log.debug(
        "starting node %s:%s in project %s for user %s",
        service_key,
        service_version,
        project["uuid"],
        user_id,
        extra=get_log_record_extra(user_id=user_id),
    )
    node_uuid = NodeID(service_id if service_id else f"{uuid4()}")
    default_resources = await catalog_client.get_service_resources(
        request.app, user_id, service_key, service_version
    )
    db: ProjectDBAPI = request.app[APP_PROJECT_DBAPI]
    assert db  # nosec
    await db.add_project_node(
        user_id,
        ProjectID(project["uuid"]),
        ProjectNodeCreate(
            node_id=node_uuid, required_resources=jsonable_encoder(default_resources)
        ),
        Node.parse_obj(
            {
                "key": service_key,
                "version": service_version,
                "label": service_key.split("/")[-1],
            }
        ),
        product_name,
    )

    # also ensure the project is updated by director-v2 since services
    # are due to access comp_tasks at some point see [https://github.com/ITISFoundation/osparc-simcore/issues/3216]
    await director_v2_api.create_or_update_pipeline(
        request.app, user_id, project["uuid"], product_name
    )
    await director_v2_api.update_dynamic_service_networks_in_project(
        request.app, project["uuid"]
    )

    if _is_node_dynamic(service_key):
        with suppress(ProjectStartsTooManyDynamicNodesError):
            # NOTE: we do not start the service if there are already too many
            await _start_dynamic_service(
                request,
                service_key=service_key,
                service_version=service_version,
                product_name=product_name,
                user_id=user_id,
                project_uuid=ProjectID(project["uuid"]),
                node_uuid=node_uuid,
            )

    return node_uuid


async def start_project_node(
    request: web.Request,
    product_name: str,
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
):
    project = await get_project_for_user(request.app, f"{project_id}", user_id)
    workbench = project.get("workbench", {})
    if not workbench.get(f"{node_id}"):
        raise NodeNotFoundError(project_uuid=f"{project_id}", node_uuid=f"{node_id}")
    node_details = Node.construct(**workbench[f"{node_id}"])

    await _start_dynamic_service(
        request,
        service_key=node_details.key,
        service_version=node_details.version,
        product_name=product_name,
        user_id=user_id,
        project_uuid=project_id,
        node_uuid=node_id,
    )


async def _remove_service_and_its_data_folders(
    app: web.Application,
    *,
    user_id: UserID,
    project_uuid: ProjectID,
    node_uuid: NodeIDStr,
    user_agent: str,
    stop_service: bool,
) -> None:
    if stop_service:
        # no need to save the state of the node when deleting it
        await dynamic_scheduler_api.stop_dynamic_service(
            app,
            dynamic_service_stop=DynamicServiceStop(
                user_id=user_id,
                project_id=project_uuid,
                node_id=NodeID(node_uuid),
                simcore_user_agent=user_agent,
                save_state=False,
            ),
        )

    # remove the node's data if any
    await storage_api.delete_data_folders_of_project_node(
        app, f"{project_uuid}", node_uuid, user_id
    )


async def delete_project_node(
    request: web.Request, project_uuid: ProjectID, user_id: UserID, node_uuid: NodeIDStr
) -> None:
    log.debug(
        "deleting node %s in project %s for user %s", node_uuid, project_uuid, user_id
    )

    list_running_dynamic_services = await director_v2_api.list_dynamic_services(
        request.app, project_id=f"{project_uuid}", user_id=user_id
    )

    fire_and_forget_task(
        _remove_service_and_its_data_folders(
            request.app,
            user_id=user_id,
            project_uuid=project_uuid,
            node_uuid=node_uuid,
            user_agent=request.headers.get(
                X_SIMCORE_USER_AGENT, UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE
            ),
            stop_service=any(
                f"{s.node_uuid}" == node_uuid for s in list_running_dynamic_services
            ),
        ),
        task_suffix_name=f"_remove_service_and_its_data_folders_{user_id=}_{project_uuid=}_{node_uuid}",
        fire_and_forget_tasks_collection=request.app[APP_FIRE_AND_FORGET_TASKS_KEY],
    )

    # remove the node from the db
    db: ProjectDBAPI = request.app[APP_PROJECT_DBAPI]
    assert db  # nosec
    await db.remove_project_node(user_id, project_uuid, NodeID(node_uuid))
    # also ensure the project is updated by director-v2 since services
    product_name = get_product_name(request)
    await director_v2_api.create_or_update_pipeline(
        request.app, user_id, project_uuid, product_name
    )
    await director_v2_api.update_dynamic_service_networks_in_project(
        request.app, project_uuid
    )


async def update_project_linked_product(
    app: web.Application, project_id: ProjectID, product_name: str
) -> None:
    with log_context(log, level=logging.DEBUG, msg="updating project linked product"):
        db: ProjectDBAPI = app[APP_PROJECT_DBAPI]
        await db.upsert_project_linked_product(project_id, product_name)


async def update_project_node_state(
    app: web.Application,
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
    new_state: str,
) -> dict:
    log.debug(
        "updating node %s current state in project %s for user %s",
        node_id,
        project_id,
        user_id,
    )

    db: ProjectDBAPI = app[APP_PROJECT_DBAPI]
    updated_project, _ = await db.update_project_node_data(
        user_id=user_id,
        project_uuid=project_id,
        node_id=node_id,
        product_name=None,
        new_node_data={"state": {"currentStatus": new_state}},
    )
    return await add_project_states_for_user(
        user_id=user_id, project=updated_project, is_template=False, app=app
    )


async def is_project_hidden(app: web.Application, project_id: ProjectID) -> bool:
    db: ProjectDBAPI = app[APP_PROJECT_DBAPI]
    return await db.is_hidden(project_id)


async def patch_project_node(
    app: web.Application,
    *,
    product_name: ProductName,
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
    node_patch: NodePatch,
) -> None:
    _node_patch_exclude_unset: dict[str, Any] = jsonable_encoder(
        node_patch, exclude_unset=True, by_alias=True
    )
    db: ProjectDBAPI = app[APP_PROJECT_DBAPI]

    # 1. Check user permissions
    _user_project_access_rights = await db.get_project_access_rights_for_user(
        user_id, project_id
    )
    if not _user_project_access_rights.write:
        raise ProjectInvalidRightsError(user_id=user_id, project_uuid=project_id)

    # 2. If patching service key or version make sure it's valid
    if _node_patch_exclude_unset.get("key") or _node_patch_exclude_unset.get("version"):
        _project, _ = await db.get_project(
            user_id=user_id, project_uuid=f"{project_id}"
        )
        _project_node_data = _project["workbench"][f"{node_id}"]

        _service_key = _node_patch_exclude_unset.get("key", _project_node_data["key"])
        _service_version = _node_patch_exclude_unset.get(
            "version", _project_node_data["version"]
        )
        rabbitmq_rpc_client = get_rabbitmq_rpc_client(app)
        await catalog_rpc.check_for_service(
            rabbitmq_rpc_client,
            product_name=product_name,
            user_id=user_id,
            service_key=_service_key,
            service_version=_service_version,
        )

    # 3. Patch the project node
    updated_project, _ = await db.update_project_node_data(
        user_id=user_id,
        project_uuid=project_id,
        node_id=node_id,
        product_name=product_name,
        new_node_data=_node_patch_exclude_unset,
    )

    # 4. Make calls to director-v2 to keep data in sync (ex. comp_tasks DB table)
    await director_v2_api.create_or_update_pipeline(
        app, user_id, project_id, product_name=product_name
    )
    if _node_patch_exclude_unset.get("label"):
        await director_v2_api.update_dynamic_service_networks_in_project(
            app, project_id
        )

    # 5. Notify project node update
    await notify_project_node_update(app, updated_project, node_id, errors=None)


async def update_project_node_outputs(
    app: web.Application,
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
    new_outputs: dict | None,
    new_run_hash: str | None,
) -> tuple[dict, list[str]]:
    """
    Updates outputs of a given node in a project with 'data'
    """
    log.debug(
        "updating node %s outputs in project %s for user %s with %s: run_hash [%s]",
        node_id,
        project_id,
        user_id,
        json_dumps(new_outputs),
        new_run_hash,
        extra=get_log_record_extra(user_id=user_id),
    )
    new_outputs = new_outputs or {}

    db: ProjectDBAPI = app[APP_PROJECT_DBAPI]
    updated_project, changed_entries = await db.update_project_node_data(
        user_id=user_id,
        project_uuid=project_id,
        node_id=node_id,
        product_name=None,
        new_node_data={"outputs": new_outputs, "runHash": new_run_hash},
    )

    log.debug(
        "patched project %s, following entries changed: %s",
        project_id,
        pformat(changed_entries),
    )
    updated_project = await add_project_states_for_user(
        user_id=user_id, project=updated_project, is_template=False, app=app
    )

    # changed entries come in the form of {node_uuid: {outputs: {changed_key1: value1, changed_key2: value2}}}
    # we do want only the key names
    changed_keys = (
        changed_entries.get(NodeIDStr(f"{node_id}"), {}).get("outputs", {}).keys()
    )
    return updated_project, changed_keys


async def list_node_ids_in_project(
    app: web.Application,
    project_uuid: ProjectID,
) -> set[NodeID]:
    """Returns a set with all the node_ids from a project's workbench"""
    db: ProjectDBAPI = app[APP_PROJECT_DBAPI]
    return await db.list_node_ids_in_project(project_uuid)


async def is_node_id_present_in_any_project_workbench(
    app: web.Application,
    node_id: NodeID,
) -> bool:
    """If the node_id is presnet in one of the projects' workbenche returns True"""
    db: ProjectDBAPI = app[APP_PROJECT_DBAPI]
    return await db.node_id_exists(node_id)


async def _trigger_connected_service_retrieve(
    app: web.Application, project: dict, updated_node_uuid: str, changed_keys: list[str]
) -> None:
    project_id = project["uuid"]
    if await is_project_locked(app, project_id):
        # NOTE: we log warn since this function is fire&forget and raise an exception would not be anybody to handle it
        log.warning(
            "Skipping service retrieval because project with %s is currently locked."
            "Operation triggered by %s",
            f"{project_id=}",
            f"{changed_keys=}",
        )
        return

    workbench = project["workbench"]
    nodes_keys_to_update: dict[str, list[str]] = defaultdict(list)

    # find the nodes that need to retrieve data
    for node_uuid, node in workbench.items():
        # check this node is dynamic
        if not _is_node_dynamic(node["key"]):
            continue

        # check whether this node has our updated node as linked inputs
        node_inputs = node.get("inputs", {})
        for port_key, port_value in node_inputs.items():
            # we look for node port links, not values
            if not isinstance(port_value, dict):
                continue

            input_node_uuid = port_value.get("nodeUuid")
            if input_node_uuid != updated_node_uuid:
                continue
            # so this node is linked to the updated one, now check if the port was changed?
            linked_input_port = port_value.get("output")
            if linked_input_port in changed_keys:
                nodes_keys_to_update[node_uuid].append(port_key)

    # call /retrieve on the nodes
    update_tasks = [
        director_v2_api.request_retrieve_dyn_service(app, node, keys)
        for node, keys in nodes_keys_to_update.items()
    ]
    await logged_gather(*update_tasks)


async def post_trigger_connected_service_retrieve(
    app: web.Application,
    *,
    project: dict,
    updated_node_uuid: str,
    changed_keys: list[str],
) -> None:
    await fire_and_forget_task(
        _trigger_connected_service_retrieve(
            app,
            project=project,
            updated_node_uuid=updated_node_uuid,
            changed_keys=changed_keys,
        ),
        task_suffix_name="trigger_connected_service_retrieve",
        fire_and_forget_tasks_collection=app[APP_FIRE_AND_FORGET_TASKS_KEY],
    )


#
# OPEN PROJECT -------------------------------------------------------------------
#


async def _user_has_another_client_open(
    users_sessions_ids: list[UserSessionID], app: web.Application
) -> bool:
    # NOTE if there is an active socket in use, that means the client is active
    for u in users_sessions_ids:
        with managed_resource(u.user_id, u.client_session_id, app) as user_session:
            if await user_session.get_socket_id() is not None:
                return True
    return False


async def _clean_user_disconnected_clients(
    users_sessions_ids: list[UserSessionID], app: web.Application
):
    for u in users_sessions_ids:
        with managed_resource(u.user_id, u.client_session_id, app) as user_session:
            if await user_session.get_socket_id() is None:
                log.debug(
                    "removing disconnected project of user %s/%s",
                    u.user_id,
                    u.client_session_id,
                )
                await user_session.remove(PROJECT_ID_KEY)


async def try_open_project_for_user(
    user_id: UserID,
    project_uuid: str,
    client_session_id: str,
    app: web.Application,
    max_number_of_studies_per_user: int | None,
) -> bool:
    """
    Raises:
        ProjectTooManyProjectOpenedError: maximum limit of projects (`max_number_of_studies_per_user`) reached

    Returns:
        False if cannot be opened (e.g. locked, )
    """
    try:
        async with lock_with_notification(
            app,
            project_uuid,
            ProjectStatus.OPENING,
            user_id,
            await get_user_fullname(app, user_id),
            notify_users=False,
        ):
            with managed_resource(user_id, client_session_id, app) as user_session:
                # NOTE: if max_number_of_studies_per_user is set, the same
                # project shall still be openable if the tab was closed
                if max_number_of_studies_per_user is not None and (
                    len(
                        {
                            uuid
                            for uuid in await user_session.find_all_resources_of_user(
                                PROJECT_ID_KEY
                            )
                            if uuid != project_uuid
                        }
                    )
                    >= max_number_of_studies_per_user
                ):
                    raise ProjectTooManyProjectOpenedError(
                        max_num_projects=max_number_of_studies_per_user
                    )

                # Assign project_id to current_session
                current_session: UserSessionID = user_session.get_id()
                sessions_with_project: list[
                    UserSessionID
                ] = await user_session.find_users_of_resource(
                    app, PROJECT_ID_KEY, project_uuid
                )
                if not sessions_with_project:
                    # no one has the project so we assign it
                    await user_session.add(PROJECT_ID_KEY, project_uuid)
                    return True

                # Otherwise if this is the only user (NOTE: a session = user_id + client_seesion_id !)
                user_ids: set[int] = {s.user_id for s in sessions_with_project}
                if user_ids.issubset({user_id}):
                    other_sessions_with_project = [
                        usid
                        for usid in sessions_with_project
                        if usid != current_session
                    ]
                    if not await _user_has_another_client_open(
                        other_sessions_with_project,
                        app,
                    ):
                        # steal the project
                        await user_session.add(PROJECT_ID_KEY, project_uuid)
                        await _clean_user_disconnected_clients(
                            sessions_with_project, app
                        )
                        return True

            return False

    except ProjectLockError:
        # the project is currently locked
        return False


#
# CLOSE PROJECT -------------------------------------------------------------------
#


async def try_close_project_for_user(
    user_id: int,
    project_uuid: str,
    client_session_id: str,
    app: web.Application,
    simcore_user_agent: str,
):
    with managed_resource(user_id, client_session_id, app) as user_session:
        current_session: UserSessionID = user_session.get_id()
        all_sessions_with_project: list[
            UserSessionID
        ] = await user_session.find_users_of_resource(
            app, key=PROJECT_ID_KEY, value=project_uuid
        )

        # first check whether other sessions registered this project
        if current_session not in all_sessions_with_project:
            # nothing to do, I do not have this project registered
            log.warning(
                "%s is not registered as resource of %s. Skipping close project",
                f"{project_uuid=}",
                f"{user_id}",
                extra=get_log_record_extra(user_id=user_id),
            )
            return

        # remove the project from our list of opened ones
        log.debug(
            "removing project [%s] from user [%s] resources", project_uuid, user_id
        )
        await user_session.remove(key=PROJECT_ID_KEY)

    # check it is not opened by someone else
    all_sessions_with_project.remove(current_session)
    log.debug("remaining user_to_session_ids: %s", all_sessions_with_project)
    if not all_sessions_with_project:
        # NOTE: depending on the garbage collector speed, it might already be removing it
        fire_and_forget_task(
            remove_project_dynamic_services(
                user_id, project_uuid, app, simcore_user_agent
            ),
            task_suffix_name=f"remove_project_dynamic_services_{user_id=}_{project_uuid=}",
            fire_and_forget_tasks_collection=app[APP_FIRE_AND_FORGET_TASKS_KEY],
        )
    else:
        log.error(
            "project [%s] is used by other users: [%s]. This should not be possible",
            project_uuid,
            {user_session.user_id for user_session in all_sessions_with_project},
        )


#
#  PROJECT STATE -------------------------------------------------------------------
#


async def _get_project_lock_state(
    user_id: int,
    project_uuid: str,
    app: web.Application,
) -> ProjectLocked:
    """returns the lock state of a project
    1. If a project is locked for any reason, first return the project as locked and STATUS defined by lock
    2. If a client_session_id is passed, then first check to see if the project is currently opened by this very user/tab combination, if yes returns the project as Locked and OPENED.
    3. If any other user than user_id is using the project (even disconnected before the TTL is finished) then the project is Locked and OPENED.
    4. If the same user is using the project with a valid socket id (meaning a tab is currently active) then the project is Locked and OPENED.
    5. If the same user is using the project with NO socket id (meaning there is no current tab active) then the project is Unlocked and OPENED. which means the user can open it again.
    """
    log.debug(
        "getting project [%s] lock state for user [%s]...",
        f"{project_uuid=}",
        f"{user_id=}",
    )
    prj_locked_state: ProjectLocked | None = await get_project_locked_state(
        app, project_uuid
    )
    if prj_locked_state:
        log.debug(
            "project [%s] is locked: %s", f"{project_uuid=}", f"{prj_locked_state=}"
        )
        return prj_locked_state

    # let's now check if anyone has the project in use somehow
    with managed_resource(user_id, None, app) as rt:
        user_session_id_list: list[UserSessionID] = await rt.find_users_of_resource(
            app, PROJECT_ID_KEY, project_uuid
        )
    set_user_ids = {user_session.user_id for user_session in user_session_id_list}

    assert (  # nosec
        len(set_user_ids) <= 1
    )  # nosec  # NOTE: A project can only be opened by one user in one tab at the moment

    if not set_user_ids:
        # no one has the project, so it is unlocked and closed.
        log.debug("project [%s] is not in use", f"{project_uuid=}")
        return ProjectLocked(value=False, status=ProjectStatus.CLOSED)

    log.debug(
        "project [%s] might be used by the following users: [%s]",
        f"{project_uuid=}",
        f"{set_user_ids=}",
    )
    usernames: list[FullNameDict] = [
        await get_user_fullname(app, uid) for uid in set_user_ids
    ]
    # let's check if the project is opened by the same user, maybe already opened or closed in a orphaned session
    if set_user_ids.issubset({user_id}):
        if not await _user_has_another_client_open(user_session_id_list, app):
            # in this case the project is re-openable by the same user until it gets closed
            log.debug(
                "project [%s] is in use by the same user [%s] that is currently disconnected, so it is unlocked for this specific user and opened",
                f"{project_uuid=}",
                f"{set_user_ids=}",
            )
            return ProjectLocked(
                value=False,
                owner=Owner(user_id=list(set_user_ids)[0], **usernames[0]),  # type: ignore[arg-type]
                status=ProjectStatus.OPENED,
            )
    # the project is opened in another tab or browser, or by another user, both case resolves to the project being locked, and opened
    log.debug(
        "project [%s] is in use by another user [%s], so it is locked",
        f"{project_uuid=}",
        f"{set_user_ids=}",
    )
    return ProjectLocked(
        value=True,
        owner=Owner(user_id=list(set_user_ids)[0], **usernames[0]),  # type: ignore[arg-type]
        status=ProjectStatus.OPENED,
    )


async def get_project_states_for_user(
    user_id: int, project_uuid: str, app: web.Application
) -> ProjectState:
    # for templates: the project is never locked and never opened. also the running state is always unknown
    lock_state = ProjectLocked(value=False, status=ProjectStatus.CLOSED)
    running_state = RunningState.UNKNOWN
    lock_state, computation_task = await logged_gather(
        _get_project_lock_state(user_id, project_uuid, app),
        director_v2_api.get_computation_task(app, user_id, UUID(project_uuid)),
    )
    if computation_task:
        # get the running state
        running_state = computation_task.state

    return ProjectState(
        locked=lock_state, state=ProjectRunningState(value=running_state)
    )


async def add_project_states_for_user(
    user_id: int,
    project: ProjectDict,
    is_template: bool,
    app: web.Application,
) -> ProjectDict:
    log.debug(
        "adding project states for %s with project %s",
        f"{user_id=}",
        f"{project['uuid']=}",
    )
    # for templates: the project is never locked and never opened. also the running state is always unknown
    lock_state = await _get_project_lock_state(user_id, project["uuid"], app)
    running_state = RunningState.UNKNOWN

    if not is_template:
        if computation_task := await director_v2_api.get_computation_task(
            app, user_id, project["uuid"]
        ):
            # get the running state
            running_state = computation_task.state
            # get the nodes individual states
            for (
                node_id,
                node_state,
            ) in computation_task.pipeline_details.node_states.items():
                prj_node = project["workbench"].get(str(node_id))
                if prj_node is None:
                    continue
                node_state_dict = json.loads(
                    node_state.json(by_alias=True, exclude_unset=True)
                )
                prj_node.setdefault("state", {}).update(node_state_dict)
                prj_node_progress = node_state_dict.get("progress", None) or 0
                prj_node.update({"progress": round(prj_node_progress * 100.0)})

    project["state"] = ProjectState(
        locked=lock_state, state=ProjectRunningState(value=running_state)
    ).dict(by_alias=True, exclude_unset=True)
    return project


#
# SERVICE DEPRECATION ----------------------------
#
async def is_service_deprecated(
    app: web.Application,
    user_id: UserID,
    service_key: str,
    service_version: str,
    product_name: str,
) -> bool:
    service = await catalog_client.get_service(
        app, user_id, service_key, service_version, product_name
    )
    if deprecation_date := service.get("deprecated"):
        deprecation_date = parse_obj_as(datetime.datetime, deprecation_date)
        deprecation_date_bool: bool = datetime.datetime.utcnow() > deprecation_date
        return deprecation_date_bool
    return False


async def is_project_node_deprecated(
    app: web.Application,
    user_id: UserID,
    project: dict[str, Any],
    node_id: NodeID,
    product_name: str,
) -> bool:
    if project_node := project.get("workbench", {}).get(f"{node_id}"):
        return await is_service_deprecated(
            app, user_id, project_node["key"], project_node["version"], product_name
        )
    raise NodeNotFoundError(project_uuid=project["uuid"], node_uuid=f"{node_id}")


#
# SERVICE RESOURCES -----------------------------------
#


async def get_project_node_resources(
    app: web.Application,
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
    service_key: str,
    service_version: str,
) -> ServiceResourcesDict:
    db = ProjectDBAPI.get_from_app_context(app)
    try:
        project_node = await db.get_project_node(project_id, node_id)
        node_resources = parse_obj_as(
            ServiceResourcesDict, project_node.required_resources
        )
        if not node_resources:
            # get default resources
            node_resources = await catalog_client.get_service_resources(
                app, user_id, service_key, service_version
            )
        return node_resources

    except ProjectNodesNodeNotFoundError as exc:
        raise NodeNotFoundError(
            project_uuid=f"{project_id}", node_uuid=f"{node_id}"
        ) from exc


async def update_project_node_resources(
    app: web.Application,
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
    service_key: str,
    service_version: str,
    product_name: str,
    resources: ServiceResourcesDict,
) -> ServiceResourcesDict:
    db = ProjectDBAPI.get_from_app_context(app)
    try:
        # validate the resource are applied to the same container names
        current_project_node = await db.get_project_node(project_id, node_id)
        current_resources = parse_obj_as(
            ServiceResourcesDict, current_project_node.required_resources
        )
        if not current_resources:
            # NOTE: this can happen after the migration
            # get default resources
            current_resources = await catalog_client.get_service_resources(
                app, user_id, service_key, service_version
            )

        validate_new_service_resources(current_resources, new_resources=resources)
        set_reservation_same_as_limit(resources)

        project_node = await db.update_project_node(
            user_id=user_id,
            project_id=project_id,
            node_id=node_id,
            product_name=product_name,
            required_resources=jsonable_encoder(resources),
            check_update_allowed=True,
        )
        return parse_obj_as(ServiceResourcesDict, project_node.required_resources)
    except ProjectNodesNodeNotFoundError as exc:
        raise NodeNotFoundError(
            project_uuid=f"{project_id}", node_uuid=f"{node_id}"
        ) from exc


#
# PROJECT DYNAMIC SERVICES -----------------------------------------------------
#


async def run_project_dynamic_services(
    request: web.Request,
    project: dict,
    user_id: UserID,
    product_name: str,
) -> None:
    # first get the services if they already exist
    project_settings: ProjectsSettings = get_plugin_settings(request.app)
    running_services_uuids: list[NodeIDStr] = [
        NodeIDStr(f"{d.node_uuid}")
        for d in await director_v2_api.list_dynamic_services(
            request.app, user_id, project["uuid"]
        )
    ]

    # find what needs to be started
    services_to_start_uuids: dict[NodeIDStr, dict[str, Any]] = {
        service_uuid: service
        for service_uuid, service in project["workbench"].items()
        if _is_node_dynamic(service["key"])
        and service_uuid not in running_services_uuids
    }
    if project_settings.PROJECTS_MAX_NUM_RUNNING_DYNAMIC_NODES > 0 and (
        (len(services_to_start_uuids) + len(running_services_uuids))
        > project_settings.PROJECTS_MAX_NUM_RUNNING_DYNAMIC_NODES
    ):
        # we cannot start so many services so we are done
        raise ProjectStartsTooManyDynamicNodesError(
            user_id=user_id, project_uuid=ProjectID(project["uuid"])
        )

    # avoid starting deprecated services
    deprecated_services: list[bool] = await logged_gather(
        *(
            is_service_deprecated(
                request.app,
                user_id,
                services_to_start_uuids[service_uuid]["key"],
                services_to_start_uuids[service_uuid]["version"],
                product_name,
            )
            for service_uuid in services_to_start_uuids
        ),
        reraise=True,
    )

    await logged_gather(
        *(
            _start_dynamic_service(
                request,
                service_key=services_to_start_uuids[service_uuid]["key"],
                service_version=services_to_start_uuids[service_uuid]["version"],
                product_name=product_name,
                user_id=user_id,
                project_uuid=project["uuid"],
                node_uuid=NodeID(service_uuid),
                graceful_start=True,
            )
            for service_uuid, is_deprecated in zip(
                services_to_start_uuids, deprecated_services, strict=True
            )
            if not is_deprecated
        ),
        reraise=True,
    )


async def remove_project_dynamic_services(
    user_id: int,
    project_uuid: str,
    app: web.Application,
    simcore_user_agent: str,
    *,
    notify_users: bool = True,
    user_name: FullNameDict | None = None,
) -> None:
    """

    :raises UserNotFoundError:
    :raises ProjectLockError
    """

    # NOTE: during the closing process, which might take awhile,
    # the project is locked so no one opens it at the same time
    log.debug(
        "removing project interactive services for project [%s] and user [%s]",
        project_uuid,
        user_id,
    )

    user_name_data: FullNameDict = user_name or await get_user_fullname(app, user_id)

    user_role: UserRole | None = None
    try:
        user_role = await get_user_role(app, user_id)
    except UserNotFoundError:
        user_role = None

    save_state = await ProjectDBAPI.get_from_app_context(app).has_permission(
        user_id=user_id, project_uuid=project_uuid, permission="write"
    )
    if user_role is None or user_role <= UserRole.GUEST:
        save_state = False
    # -------------------

    async with lock_with_notification(
        app,
        project_uuid,
        ProjectStatus.CLOSING,
        user_id,
        user_name_data,
        notify_users=notify_users,
    ):
        # save the state if the user is not a guest. if we do not know we save in any case.
        with suppress(
            RPCServerError,
            ServiceWaitingForManualInterventionError,
            ServiceWasNotFoundError,
        ):
            # here RPC exceptions are suppressed. in case the service is not found to preserve old behavior
            await dynamic_scheduler_api.stop_dynamic_services_in_project(
                app=app,
                user_id=user_id,
                project_id=project_uuid,
                simcore_user_agent=simcore_user_agent,
                save_state=save_state,
            )


#
# NOTIFICATIONS & LOCKS -----------------------------------------------------
#


async def notify_project_state_update(
    app: web.Application,
    project: ProjectDict,
    notify_only_user: UserID | None = None,
) -> None:
    if await is_project_hidden(app, ProjectID(project["uuid"])):
        return
    message = SocketMessageDict(
        event_type=SOCKET_IO_PROJECT_UPDATED_EVENT,
        data={
            "project_uuid": project["uuid"],
            "data": project["state"],
        },
    )

    if notify_only_user:
        await send_message_to_user(
            app,
            user_id=notify_only_user,
            message=message,
            ignore_queue=True,
        )
    else:
        rooms_to_notify: Generator[GroupID, None, None] = (
            gid for gid, rights in project["accessRights"].items() if rights["read"]
        )
        for room in rooms_to_notify:
            await send_message_to_standard_group(app, group_id=room, message=message)


async def notify_project_node_update(
    app: web.Application,
    project: dict,
    node_id: NodeID,
    errors: list[ErrorDict] | None,
) -> None:
    if await is_project_hidden(app, ProjectID(project["uuid"])):
        return

    rooms_to_notify: list[GroupID] = [
        gid for gid, rights in project["accessRights"].items() if rights["read"]
    ]

    message = SocketMessageDict(
        event_type=SOCKET_IO_NODE_UPDATED_EVENT,
        data={
            "project_id": project["uuid"],
            "node_id": f"{node_id}",
            # as GET projects/{project_id}/nodes/{node_id}
            "data": project["workbench"][f"{node_id}"],
            # as GET projects/{project_id}/nodes/{node_id}/errors
            "errors": errors,
        },
    )

    for room in rooms_to_notify:
        await send_message_to_standard_group(app, room, message)


async def retrieve_and_notify_project_locked_state(
    user_id: int,
    project_uuid: str,
    app: web.Application,
    notify_only_prj_user: bool = False,
):
    project = await get_project_for_user(app, project_uuid, user_id, include_state=True)
    await notify_project_state_update(
        app, project, notify_only_user=user_id if notify_only_prj_user else None
    )


@contextlib.asynccontextmanager
async def lock_with_notification(
    app: web.Application,
    project_uuid: str,
    status: ProjectStatus,
    user_id: int,
    user_name: FullNameDict,
    *,
    notify_users: bool = True,
):
    try:
        async with lock_project(
            app,
            project_uuid,
            status,
            user_id,
            user_name,
        ):
            if notify_users:
                await retrieve_and_notify_project_locked_state(
                    user_id, project_uuid, app
                )
            yield
    except ProjectLockError:
        # someone else has already the lock?
        prj_states: ProjectState = await get_project_states_for_user(
            user_id, project_uuid, app
        )
        log.exception(
            "Project [%s] already locked in state '%s'. Please check with support.",
            f"{project_uuid=}",
            f"{prj_states.locked.status=}",
        )
        raise
    finally:
        if notify_users:
            await retrieve_and_notify_project_locked_state(user_id, project_uuid, app)


async def get_project_inactivity(
    app: web.Application, project_id: ProjectID
) -> GetProjectInactivityResponse:
    project_settings: ProjectsSettings = get_plugin_settings(app)
    project_inactivity = await director_v2_api.get_project_inactivity(
        app,
        project_id,
        # NOTE: project is considered inactive if all services exposing an /inactivity
        # endpoint were inactive since at least PROJECTS_INACTIVITY_INTERVAL
        max_inactivity_seconds=int(
            project_settings.PROJECTS_INACTIVITY_INTERVAL.total_seconds()
        ),
    )
    return parse_obj_as(GetProjectInactivityResponse, project_inactivity)

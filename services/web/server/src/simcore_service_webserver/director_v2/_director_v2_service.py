import logging
from uuid import UUID

from aiohttp import web
from models_library.api_schemas_directorv2.computations import (
    TasksOutputs,
    TasksSelection,
)
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.projects_pipeline import ComputationTask
from models_library.users import UserID
from models_library.utils.fastapi_encoders import jsonable_encoder
from models_library.wallets import WalletID, WalletInfo
from pydantic import TypeAdapter
from pydantic.types import PositiveInt
from servicelib.aiohttp import status
from servicelib.logging_errors import create_troubleshotting_log_kwargs
from servicelib.logging_utils import log_decorator
from simcore_postgres_database.utils_groups_extra_properties import (
    GroupExtraProperties,
    GroupExtraPropertiesRepo,
)

from ..application_settings import get_application_settings
from ..db.plugin import get_database_engine
from ..products import products_service
from ..products.models import Product
from ..projects import projects_wallets_service
from ..users import preferences_api as user_preferences_service
from ..users.exceptions import UserDefaultWalletNotFoundError
from ..wallets import api as wallets_service
from ._client import DirectorV2RestClient
from ._client_base import DataType, request_director_v2
from .exceptions import ComputationNotFoundError, DirectorV2ServiceError
from .settings import DirectorV2Settings, get_plugin_settings

_logger = logging.getLogger(__name__)


#
# PIPELINE RESOURCE ----------------------
#


@log_decorator(logger=_logger)
async def create_or_update_pipeline(
    app: web.Application,
    user_id: UserID,
    project_id: ProjectID,
    product_name: ProductName,
    product_api_base_url: str,
) -> DataType | None:
    # NOTE https://github.com/ITISFoundation/osparc-simcore/issues/7527
    settings: DirectorV2Settings = get_plugin_settings(app)

    backend_url = settings.base_url / "computations"
    body = {
        "user_id": user_id,
        "project_id": f"{project_id}",
        "product_name": product_name,
        "product_api_base_url": product_api_base_url,
        "wallet_info": await get_wallet_info(
            app,
            product=products_service.get_product(app, product_name),
            user_id=user_id,
            project_id=project_id,
            product_name=product_name,
        ),
    }

    try:
        computation_task_out = await request_director_v2(
            app, "POST", backend_url, expected_status=web.HTTPCreated, data=body
        )
        assert isinstance(computation_task_out, dict)  # nosec
        return computation_task_out

    except DirectorV2ServiceError as exc:
        _logger.exception(
            **create_troubleshotting_log_kwargs(
                f"Could not create pipeline from project {project_id}",
                error=exc,
                error_context={**body, "backend_url": backend_url},
            )
        )
    return None


@log_decorator(logger=_logger)
async def is_pipeline_running(
    app: web.Application, user_id: PositiveInt, project_id: UUID
) -> bool | None:
    # NOTE: possiblity to make it cheaper by /computations/{project_id}/state. First trial shows
    # that the efficiency gain is minimal but should be considered specially if the handler
    # gets heavier with time
    pipeline = await get_computation_task(app, user_id, project_id)
    if pipeline is None:
        # NOTE: at the time of this modification, error handling in `get_computation_task`
        # is still limited and any type of errors is transformed into a None. Therefore
        # at this point we cannot discern whether the pipeline is running or not.
        # In order to define the "UNKNOWN" state we return None, which in an
        # if statement casts to False
        return None

    pipeline_state: bool | None = pipeline.state.is_running()
    return pipeline_state


@log_decorator(logger=_logger)
async def get_computation_task(
    app: web.Application, user_id: UserID, project_id: ProjectID
) -> ComputationTask | None:

    try:
        dv2_computation = await DirectorV2RestClient(app).get_computation(
            project_id=project_id, user_id=user_id
        )
        task_out = ComputationTask.model_validate(dv2_computation, from_attributes=True)
        _logger.debug("found computation task: %s", f"{task_out=}")

        return task_out
    except DirectorV2ServiceError as exc:
        if exc.status == status.HTTP_404_NOT_FOUND:
            # the pipeline might not exist and that is ok
            return None
        _logger.warning(
            "getting pipeline for project %s failed: %s.", f"{project_id=}", exc
        )
        return None


@log_decorator(logger=_logger)
async def stop_pipeline(
    app: web.Application, *, user_id: PositiveInt, project_id: ProjectID
):
    await DirectorV2RestClient(app).stop_computation(
        project_id=project_id, user_id=user_id
    )


@log_decorator(logger=_logger)
async def delete_pipeline(
    app: web.Application,
    user_id: PositiveInt,
    project_id: ProjectID,
    *,
    force: bool = True,
) -> None:
    # NOTE https://github.com/ITISFoundation/osparc-simcore/issues/7527

    settings: DirectorV2Settings = get_plugin_settings(app)
    await request_director_v2(
        app,
        "DELETE",
        url=settings.base_url / f"computations/{project_id}",
        expected_status=web.HTTPNoContent,
        data={
            "user_id": user_id,
            "force": force,
        },
    )


#
# COMPUTATIONS TASKS RESOURCE ----------------------
#


async def get_batch_tasks_outputs(
    app: web.Application,
    *,
    project_id: ProjectID,
    selection: TasksSelection,
) -> TasksOutputs:
    # NOTE https://github.com/ITISFoundation/osparc-simcore/issues/7527
    settings: DirectorV2Settings = get_plugin_settings(app)
    response_payload = await request_director_v2(
        app,
        "POST",
        url=(settings.base_url / f"computations/{project_id}/tasks/-/outputs:batchGet"),
        expected_status=web.HTTPOk,
        data=jsonable_encoder(
            selection,
            by_alias=True,
            exclude_unset=True,
        ),
        on_error={
            status.HTTP_404_NOT_FOUND: (
                ComputationNotFoundError,
                {"project_id": f"{project_id}"},
            )
        },
    )
    assert isinstance(response_payload, dict)  # nosec
    return TasksOutputs(**response_payload)


async def get_wallet_info(
    app: web.Application,
    *,
    product: Product,
    user_id: UserID,
    project_id: ProjectID,
    product_name: ProductName,
) -> WalletInfo | None:
    app_settings = get_application_settings(app)
    if not (
        product.is_payment_enabled and app_settings.WEBSERVER_CREDIT_COMPUTATION_ENABLED
    ):
        return None
    project_wallet = await projects_wallets_service.get_project_wallet(
        app, project_id=project_id
    )
    if project_wallet is None:
        user_default_wallet_preference = await user_preferences_service.get_frontend_user_preference(
            app,
            user_id=user_id,
            product_name=product_name,
            preference_class=user_preferences_service.PreferredWalletIdFrontendUserPreference,
        )
        if user_default_wallet_preference is None:
            raise UserDefaultWalletNotFoundError(uid=user_id)
        project_wallet_id = TypeAdapter(WalletID).validate_python(
            user_default_wallet_preference.value
        )
        await projects_wallets_service.connect_wallet_to_project(
            app,
            product_name=product_name,
            project_id=project_id,
            user_id=user_id,
            wallet_id=project_wallet_id,
        )
    else:
        project_wallet_id = project_wallet.wallet_id

    # Check whether user has access to the wallet
    wallet = await wallets_service.get_wallet_with_available_credits_by_user_and_wallet(
        app,
        user_id=user_id,
        wallet_id=project_wallet_id,
        product_name=product_name,
    )
    return WalletInfo(
        wallet_id=project_wallet_id,
        wallet_name=wallet.name,
        wallet_credit_amount=wallet.available_credits,
    )


async def get_group_properties(
    app: web.Application,
    *,
    product_name: ProductName,
    user_id: UserID,
) -> GroupExtraProperties:
    async with get_database_engine(app).acquire() as conn:
        return await GroupExtraPropertiesRepo.get_aggregated_properties_for_user(
            conn, user_id=user_id, product_name=product_name
        )

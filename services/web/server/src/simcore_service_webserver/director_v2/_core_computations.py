""" Computations API

Wraps interactions to the director-v2 service

"""

import logging
from typing import Any
from uuid import UUID

from aiohttp import web
from common_library.serialization import model_dump_with_secrets
from models_library.api_schemas_directorv2.clusters import (
    ClusterCreate,
    ClusterDetails,
    ClusterGet,
    ClusterPatch,
    ClusterPing,
)
from models_library.api_schemas_directorv2.comp_tasks import (
    TasksOutputs,
    TasksSelection,
)
from models_library.clusters import ClusterID
from models_library.projects import ProjectID
from models_library.projects_pipeline import ComputationTask
from models_library.users import UserID
from models_library.utils.fastapi_encoders import jsonable_encoder
from pydantic import TypeAdapter
from pydantic.types import PositiveInt
from servicelib.aiohttp import status
from servicelib.logging_utils import log_decorator

from ..products.api import get_product
from ._api_utils import get_wallet_info
from ._core_base import DataType, request_director_v2
from .exceptions import (
    ClusterAccessForbidden,
    ClusterDefinedPingError,
    ClusterNotFoundError,
    ClusterPingError,
    ComputationNotFoundError,
    DirectorServiceError,
)
from .settings import DirectorV2Settings, get_plugin_settings

_logger = logging.getLogger(__name__)


class ComputationsApi:
    def __init__(self, app: web.Application) -> None:
        self._app = app
        self._settings: DirectorV2Settings = get_plugin_settings(app)

    async def get(self, project_id: ProjectID, user_id: UserID) -> dict[str, Any]:
        computation_task_out = await request_director_v2(
            self._app,
            "GET",
            (self._settings.base_url / "computations" / f"{project_id}").with_query(
                user_id=int(user_id)
            ),
            expected_status=web.HTTPOk,
        )
        assert isinstance(computation_task_out, dict)  # nosec
        return computation_task_out

    async def start(
        self, project_id: ProjectID, user_id: UserID, product_name: str, **options
    ) -> str:
        computation_task_out = await request_director_v2(
            self._app,
            "POST",
            self._settings.base_url / "computations",
            expected_status=web.HTTPCreated,
            data={
                "user_id": user_id,
                "project_id": project_id,
                "product_name": product_name,
                **options,
            },
        )
        assert isinstance(computation_task_out, dict)  # nosec
        computation_task_out_id: str = computation_task_out["id"]
        return computation_task_out_id

    async def stop(self, project_id: ProjectID, user_id: UserID):
        await request_director_v2(
            self._app,
            "POST",
            self._settings.base_url / "computations" / f"{project_id}:stop",
            expected_status=web.HTTPAccepted,
            data={"user_id": user_id},
        )


_APP_KEY = f"{__name__}.{ComputationsApi.__name__}"


def get_client(app: web.Application) -> ComputationsApi | None:
    app_key: ComputationsApi | None = app.get(_APP_KEY)
    return app_key


def set_client(app: web.Application, obj: ComputationsApi):
    app[_APP_KEY] = obj


#
# PIPELINE RESOURCE ----------------------
#
# TODO: REFACTOR! the client class above and the free functions below are duplicates of the same interface!


@log_decorator(logger=_logger)
async def create_or_update_pipeline(
    app: web.Application, user_id: UserID, project_id: ProjectID, product_name: str
) -> DataType | None:
    settings: DirectorV2Settings = get_plugin_settings(app)

    backend_url = settings.base_url / "computations"
    body = {
        "user_id": user_id,
        "project_id": f"{project_id}",
        "product_name": product_name,
        "wallet_info": await get_wallet_info(
            app,
            product=get_product(app, product_name),
            user_id=user_id,
            project_id=project_id,
            product_name=product_name,
        ),
    }
    # request to director-v2
    try:
        computation_task_out = await request_director_v2(
            app, "POST", backend_url, expected_status=web.HTTPCreated, data=body
        )
        assert isinstance(computation_task_out, dict)  # nosec
        return computation_task_out

    except DirectorServiceError as exc:
        _logger.error(  # noqa: TRY400
            "could not create pipeline from project %s: %s",
            project_id,
            exc,
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
    settings: DirectorV2Settings = get_plugin_settings(app)
    backend_url = (settings.base_url / f"computations/{project_id}").update_query(
        user_id=int(user_id)
    )

    # request to director-v2
    try:
        computation_task_out_dict = await request_director_v2(
            app, "GET", backend_url, expected_status=web.HTTPOk
        )
        task_out = ComputationTask.model_validate(computation_task_out_dict)
        _logger.debug("found computation task: %s", f"{task_out=}")
        return task_out
    except DirectorServiceError as exc:
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
    settings: DirectorV2Settings = get_plugin_settings(app)
    await request_director_v2(
        app,
        "POST",
        url=settings.base_url / f"computations/{project_id}:stop",
        expected_status=web.HTTPAccepted,
        data={"user_id": user_id},
    )


@log_decorator(logger=_logger)
async def delete_pipeline(
    app: web.Application,
    user_id: PositiveInt,
    project_id: ProjectID,
    *,
    force: bool = True,
) -> None:
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
# CLUSTER RESOURCE ----------------------
#


@log_decorator(logger=_logger)
async def create_cluster(
    app: web.Application, user_id: UserID, new_cluster: ClusterCreate
) -> DataType:
    settings: DirectorV2Settings = get_plugin_settings(app)
    cluster = await request_director_v2(
        app,
        "POST",
        url=(settings.base_url / "clusters").update_query(user_id=int(user_id)),
        expected_status=web.HTTPCreated,
        data=model_dump_with_secrets(
            new_cluster, show_secrets=True, by_alias=True, exclude_unset=True
        ),
    )
    assert isinstance(cluster, dict)  # nosec
    assert ClusterGet.model_validate(cluster) is not None  # nosec
    return cluster


async def list_clusters(app: web.Application, user_id: UserID) -> list[DataType]:
    settings: DirectorV2Settings = get_plugin_settings(app)
    clusters = await request_director_v2(
        app,
        "GET",
        url=(settings.base_url / "clusters").update_query(user_id=int(user_id)),
        expected_status=web.HTTPOk,
    )

    assert isinstance(clusters, list)  # nosec
    assert TypeAdapter(list[ClusterGet]).validate_python(clusters) is not None  # nosec
    return clusters


async def get_cluster(
    app: web.Application, user_id: UserID, cluster_id: ClusterID
) -> DataType:
    settings: DirectorV2Settings = get_plugin_settings(app)
    cluster = await request_director_v2(
        app,
        "GET",
        url=(settings.base_url / f"clusters/{cluster_id}").update_query(
            user_id=int(user_id)
        ),
        expected_status=web.HTTPOk,
        on_error={
            status.HTTP_404_NOT_FOUND: (
                ClusterNotFoundError,
                {"cluster_id": cluster_id},
            ),
            status.HTTP_403_FORBIDDEN: (
                ClusterAccessForbidden,
                {"cluster_id": cluster_id},
            ),
        },
    )

    assert isinstance(cluster, dict)  # nosec
    assert ClusterGet.model_validate(cluster) is not None  # nosec
    return cluster


async def get_cluster_details(
    app: web.Application, user_id: UserID, cluster_id: ClusterID
) -> DataType:
    settings: DirectorV2Settings = get_plugin_settings(app)

    cluster = await request_director_v2(
        app,
        "GET",
        url=(settings.base_url / f"clusters/{cluster_id}/details").update_query(
            user_id=int(user_id)
        ),
        expected_status=web.HTTPOk,
        on_error={
            status.HTTP_404_NOT_FOUND: (
                ClusterNotFoundError,
                {"cluster_id": cluster_id},
            ),
            status.HTTP_403_FORBIDDEN: (
                ClusterAccessForbidden,
                {"cluster_id": cluster_id},
            ),
        },
    )
    assert isinstance(cluster, dict)  # nosec
    assert ClusterDetails.model_validate(cluster) is not None  # nosec
    return cluster


async def update_cluster(
    app: web.Application,
    user_id: UserID,
    cluster_id: ClusterID,
    cluster_patch: ClusterPatch,
) -> DataType:
    settings: DirectorV2Settings = get_plugin_settings(app)
    cluster = await request_director_v2(
        app,
        "PATCH",
        url=(settings.base_url / f"clusters/{cluster_id}").update_query(
            user_id=int(user_id)
        ),
        expected_status=web.HTTPOk,
        data=model_dump_with_secrets(
            cluster_patch, show_secrets=True, by_alias=True, exclude_none=True
        ),
        on_error={
            status.HTTP_404_NOT_FOUND: (
                ClusterNotFoundError,
                {"cluster_id": cluster_id},
            ),
            status.HTTP_403_FORBIDDEN: (
                ClusterAccessForbidden,
                {"cluster_id": cluster_id},
            ),
        },
    )

    assert isinstance(cluster, dict)  # nosec
    assert ClusterGet.model_validate(cluster) is not None  # nosec
    return cluster


async def delete_cluster(
    app: web.Application, user_id: UserID, cluster_id: ClusterID
) -> None:
    settings: DirectorV2Settings = get_plugin_settings(app)
    await request_director_v2(
        app,
        "DELETE",
        url=(settings.base_url / f"clusters/{cluster_id}").update_query(
            user_id=int(user_id)
        ),
        expected_status=web.HTTPNoContent,
        on_error={
            status.HTTP_404_NOT_FOUND: (
                ClusterNotFoundError,
                {"cluster_id": cluster_id},
            ),
            status.HTTP_403_FORBIDDEN: (
                ClusterAccessForbidden,
                {"cluster_id": cluster_id},
            ),
        },
    )


async def ping_cluster(app: web.Application, cluster_ping: ClusterPing) -> None:
    settings: DirectorV2Settings = get_plugin_settings(app)
    await request_director_v2(
        app,
        "POST",
        url=settings.base_url / "clusters:ping",
        expected_status=web.HTTPNoContent,
        data=model_dump_with_secrets(
            cluster_ping,
            show_secrets=True,
            by_alias=True,
            exclude_unset=True,
        ),
        on_error={
            status.HTTP_422_UNPROCESSABLE_ENTITY: (
                ClusterPingError,
                {"endpoint": f"{cluster_ping.endpoint}"},
            )
        },
    )


async def ping_specific_cluster(
    app: web.Application, user_id: UserID, cluster_id: ClusterID
) -> None:
    settings: DirectorV2Settings = get_plugin_settings(app)
    await request_director_v2(
        app,
        "POST",
        url=(settings.base_url / f"clusters/{cluster_id}:ping").update_query(
            user_id=int(user_id)
        ),
        expected_status=web.HTTPNoContent,
        on_error={
            status.HTTP_422_UNPROCESSABLE_ENTITY: (
                ClusterDefinedPingError,
                {"cluster_id": f"{cluster_id}"},
            )
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

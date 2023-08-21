""" Computations API

Wraps interactions to the director-v2 service

"""
import json
import logging
from typing import Any
from uuid import UUID

from aiohttp import web
from models_library.api_schemas_directorv2.clusters import (
    ClusterCreate,
    ClusterDetails,
    ClusterGet,
    ClusterPatch,
    ClusterPing,
)
from models_library.clusters import ClusterID
from models_library.projects import ProjectID
from models_library.projects_pipeline import ComputationTask
from models_library.users import UserID
from pydantic import parse_obj_as
from pydantic.types import PositiveInt
from servicelib.logging_utils import log_decorator
from settings_library.utils_cli import create_json_encoder_wo_secrets

from ._core_base import DataType, request_director_v2
from .exceptions import (
    ClusterAccessForbidden,
    ClusterDefinedPingError,
    ClusterNotFoundError,
    ClusterPingError,
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
    }
    # request to director-v2
    try:
        computation_task_out = await request_director_v2(
            app, "POST", backend_url, expected_status=web.HTTPCreated, data=body
        )
        assert isinstance(computation_task_out, dict)  # nosec
        return computation_task_out

    except DirectorServiceError as exc:
        _logger.error(
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
        task_out = ComputationTask.parse_obj(computation_task_out_dict)
        _logger.debug("found computation task: %s", f"{task_out=}")
        return task_out
    except DirectorServiceError as exc:
        if exc.status == web.HTTPNotFound.status_code:
            # the pipeline might not exist and that is ok
            return None
        _logger.warning(
            "getting pipeline for project %s failed: %s.", f"{project_id=}", exc
        )
        return None


@log_decorator(logger=_logger)
async def delete_pipeline(
    app: web.Application, user_id: PositiveInt, project_id: UUID
) -> None:
    settings: DirectorV2Settings = get_plugin_settings(app)

    backend_url = settings.base_url / f"computations/{project_id}"
    body = {"user_id": user_id, "force": True}

    # request to director-v2
    await request_director_v2(
        app, "DELETE", backend_url, expected_status=web.HTTPNoContent, data=body
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
        data=json.loads(
            new_cluster.json(
                by_alias=True,
                exclude_unset=True,
                encoder=create_json_encoder_wo_secrets(ClusterCreate),
            )
        ),
    )
    assert isinstance(cluster, dict)  # nosec
    assert parse_obj_as(ClusterGet, cluster) is not None  # nosec
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
    assert parse_obj_as(list[ClusterGet], clusters) is not None  # nosec
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
            web.HTTPNotFound.status_code: (
                ClusterNotFoundError,
                {"cluster_id": cluster_id},
            ),
            web.HTTPForbidden.status_code: (
                ClusterAccessForbidden,
                {"cluster_id": cluster_id},
            ),
        },
    )

    assert isinstance(cluster, dict)  # nosec
    assert parse_obj_as(ClusterGet, cluster) is not None  # nosec
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
            web.HTTPNotFound.status_code: (
                ClusterNotFoundError,
                {"cluster_id": cluster_id},
            ),
            web.HTTPForbidden.status_code: (
                ClusterAccessForbidden,
                {"cluster_id": cluster_id},
            ),
        },
    )
    assert isinstance(cluster, dict)  # nosec
    assert parse_obj_as(ClusterDetails, cluster) is not None  # nosec
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
        data=json.loads(
            cluster_patch.json(
                by_alias=True,
                exclude_unset=True,
                encoder=create_json_encoder_wo_secrets(ClusterPatch),
            )
        ),
        on_error={
            web.HTTPNotFound.status_code: (
                ClusterNotFoundError,
                {"cluster_id": cluster_id},
            ),
            web.HTTPForbidden.status_code: (
                ClusterAccessForbidden,
                {"cluster_id": cluster_id},
            ),
        },
    )

    assert isinstance(cluster, dict)  # nosec
    assert parse_obj_as(ClusterGet, cluster) is not None  # nosec
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
            web.HTTPNotFound.status_code: (
                ClusterNotFoundError,
                {"cluster_id": cluster_id},
            ),
            web.HTTPForbidden.status_code: (
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
        data=json.loads(
            cluster_ping.json(
                by_alias=True,
                exclude_unset=True,
                encoder=create_json_encoder_wo_secrets(ClusterPing),
            )
        ),
        on_error={
            web.HTTPUnprocessableEntity.status_code: (
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
            web.HTTPUnprocessableEntity.status_code: (
                ClusterDefinedPingError,
                {"cluster_id": f"{cluster_id}"},
            )
        },
    )

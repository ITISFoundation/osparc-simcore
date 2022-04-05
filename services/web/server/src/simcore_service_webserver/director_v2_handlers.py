import asyncio
import logging
from typing import Any, Dict, List, Set, Tuple

from aiohttp import web
from models_library.clusters import ClusterID
from models_library.projects import ProjectID
from models_library.users import UserID
from pydantic import BaseModel, ValidationError, parse_obj_as
from pydantic.types import NonNegativeInt
from servicelib.aiohttp.rest_responses import create_error_response, get_http_error
from servicelib.json_serialization import json_dumps

from ._meta import api_version_prefix as VTAG
from .director_v2_abc import get_project_run_policy
from .director_v2_core import DirectorServiceError, DirectorV2ApiClient
from .login.decorators import RQT_USERID_KEY, login_required
from .security_decorators import permission_required
from .version_control_db import CommitID

log = logging.getLogger(__name__)

# TODO: connect routes
routes = web.RouteTableDef()


@routes.post(f"/{VTAG}/computations/{{project_id}}:start")
@login_required
@permission_required("services.pipeline.*")
@permission_required("project.read")
async def start_computation(request: web.Request) -> web.Response:
    client = DirectorV2ApiClient(request.app)

    run_policy = get_project_run_policy(request.app)
    assert run_policy  # nosec

    user_id = UserID(request[RQT_USERID_KEY])
    project_id = ProjectID(request.match_info["project_id"])

    subgraph: Set[str] = set()
    force_restart: bool = False  # TODO: deprecate this entry
    cluster_id: NonNegativeInt = 0

    if request.can_read_body:
        body = await request.json()
        subgraph = body.get("subgraph", [])
        force_restart = bool(body.get("force_restart", force_restart))
        cluster_id = body.get("cluster_id")

    options = {
        "start_pipeline": True,
        "subgraph": list(subgraph),  # sets are not natively json serializable
        "force_restart": force_restart,
        "cluster_id": cluster_id,
    }

    try:
        running_project_ids: List[ProjectID]
        project_vc_commits: List[CommitID]

        (
            running_project_ids,
            project_vc_commits,
        ) = await run_policy.get_or_create_runnable_projects(request, project_id)
        log.debug(
            "Project %s will start %d variants: %s",
            f"{project_id=}",
            len(running_project_ids),
            f"{running_project_ids=}",
        )

        assert running_project_ids  # nosec
        assert (  # nosec
            len(running_project_ids) == len(project_vc_commits)
            if project_vc_commits
            else True
        )

        _started_pipelines_ids: Tuple[str] = await asyncio.gather(
            *[client.start(pid, user_id, **options) for pid in running_project_ids]
        )

        assert set(_started_pipelines_ids) == set(
            map(str, running_project_ids)
        )  # nosec

        data: Dict[str, Any] = {
            "pipeline_id": project_id,
        }
        # Optional
        if project_vc_commits:
            data["ref_ids"] = project_vc_commits

        return web.json_response(
            {"data": data},
            status=web.HTTPCreated.status_code,
            dumps=json_dumps,
        )

    except DirectorServiceError as exc:
        return create_error_response(
            exc,
            reason=exc.reason,
            http_error_cls=get_http_error(exc.status) or web.HTTPServiceUnavailable,
        )


@routes.post(f"/{VTAG}/computations/{{project_id}}:stop")
@login_required
@permission_required("services.pipeline.*")
@permission_required("project.read")
async def stop_computation(request: web.Request) -> web.Response:
    client = DirectorV2ApiClient(request.app)
    run_policy = get_project_run_policy(request.app)
    assert run_policy  # nosec

    user_id = UserID(request[RQT_USERID_KEY])
    project_id = ProjectID(request.match_info["project_id"])

    try:
        project_ids: List[ProjectID] = await run_policy.get_runnable_projects_ids(
            request, project_id
        )
        log.debug("Project %s will stop %d variants", project_id, len(project_ids))

        await asyncio.gather(*[client.stop(pid, user_id) for pid in project_ids])

        # FIXME: our middleware has this issue
        #
        #  if 'return web.HTTPNoContent()' then 'await response.json()' raises ContentTypeError
        #  if 'raise web.HTTPNoContent()' then 'await response.json() == None'
        #
        raise web.HTTPNoContent()

    except DirectorServiceError as exc:
        return create_error_response(
            exc,
            reason=exc.reason,
            http_error_cls=get_http_error(exc.status) or web.HTTPServiceUnavailable,
        )


class ComputationTaskGet(BaseModel):
    cluster_id: ClusterID


@routes.get(f"/{VTAG}/computations/{{project_id}}")
@login_required
@permission_required("services.pipeline.*")
@permission_required("project.read")
async def get_computation(request: web.Request) -> web.Response:
    client = DirectorV2ApiClient(request.app)
    run_policy = get_project_run_policy(request.app)
    assert run_policy  # nosec

    user_id = UserID(request[RQT_USERID_KEY])
    project_id = ProjectID(request.match_info["project_id"])

    try:
        project_ids: List[ProjectID] = await run_policy.get_runnable_projects_ids(
            request, project_id
        )
        log.debug("Project %s will get %d variants", project_id, len(project_ids))
        list_computation_tasks = parse_obj_as(
            List[ComputationTaskGet],
            await asyncio.gather(
                *[client.get(project_id=pid, user_id=user_id) for pid in project_ids]
            ),
        )
        assert len(list_computation_tasks) == len(project_ids)  # nosec
        # NOTE: until changed all the versions of a meta project shall use the same cluster
        # this should fail the day that changes
        assert all(
            c.cluster_id == list_computation_tasks[0].cluster_id
            for c in list_computation_tasks
        )
        return web.json_response(
            data={
                "data": list_computation_tasks[0].dict(
                    by_alias=True, exclude_unset=True
                )
            },
            dumps=json_dumps,
        )
    except DirectorServiceError as exc:
        return create_error_response(
            exc,
            reason=exc.reason,
            http_error_cls=get_http_error(exc.status) or web.HTTPServiceUnavailable,
        )
    except ValidationError as exc:
        return create_error_response(exc, http_error_cls=web.HTTPInternalServerError)

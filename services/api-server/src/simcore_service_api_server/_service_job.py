import logging
from collections.abc import Callable
from typing import Annotated

from fastapi import Depends
from models_library.api_schemas_webserver.projects import ProjectCreateNew, ProjectGet
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.users import UserID
from pydantic import HttpUrl
from servicelib.fastapi.app_state import SingletonInAppStateMixin
from servicelib.logging_utils import log_context
from simcore_service_api_server.api.dependencies.authentication import (
    get_current_user_id,
    get_product_name,
)
from simcore_service_api_server.api.dependencies.webserver_rpc import (
    get_wb_api_rpc_client,
)
from simcore_service_api_server.services_rpc.wb_api_server import WbApiRpcClient

from .api.dependencies.webserver_http import get_webserver_session
from .models.schemas.jobs import Job, JobInputs
from .models.schemas.programs import Program
from .models.schemas.solvers import Solver
from .services_http.solver_job_models_converters import (
    create_job_from_project,
    create_new_project_for_job,
)
from .services_http.webserver import AuthSession

_logger = logging.getLogger(__name__)


class JobService(SingletonInAppStateMixin):
    app_state_name = "JobService"
    _web_rest_api: AuthSession
    _web_rpc_api: WbApiRpcClient
    _user_id: UserID
    _product_name: ProductName

    def __init__(
        self,
        *,
        web_rest_api: Annotated[AuthSession, Depends(get_webserver_session)],
        web_rpc_api: Annotated[WbApiRpcClient, Depends(get_wb_api_rpc_client)],
        user_id: Annotated[UserID, Depends(get_current_user_id)],
        product_name: Annotated[ProductName, Depends(get_product_name)],
    ):
        self._web_rest_api = web_rest_api
        self._web_rpc_api = web_rpc_api
        self._user_id = user_id
        self._product_name = product_name

    async def create_job(
        self,
        *,
        solver_or_program: Solver | Program,
        inputs: JobInputs,
        parent_project_uuid: ProjectID | None,
        parent_node_id: NodeID | None,
        url_for: Callable[..., HttpUrl],
        hidden: bool,
        name: str | None,
        description: str | None,
    ) -> tuple[Job, ProjectGet]:
        # creates NEW job as prototype
        pre_job = Job.create_job_from_solver_or_program(
            solver_or_program_name=solver_or_program.name, inputs=inputs, name=name
        )
        with log_context(
            logger=_logger, level=logging.DEBUG, msg=f"Creating job {pre_job.name}"
        ):
            project_in: ProjectCreateNew = create_new_project_for_job(
                solver_or_program=solver_or_program,
                job=pre_job,
                inputs=inputs,
                description=description,
            )
            new_project: ProjectGet = await self._web_rest_api.create_project(
                project_in,
                is_hidden=hidden,
                parent_project_uuid=parent_project_uuid,
                parent_node_id=parent_node_id,
            )
            await self._web_rpc_api.mark_project_as_job(
                product_name=self._product_name,
                user_id=self._user_id,
                project_uuid=new_project.uuid,
                job_parent_resource_name=pre_job.runner_name,
            )

        assert new_project  # nosec
        assert new_project.uuid == pre_job.id  # nosec

        # for consistency, it rebuild job
        job = create_job_from_project(
            solver_or_program=solver_or_program, project=new_project, url_for=url_for
        )
        assert job.id == pre_job.id  # nosec
        assert job.name == pre_job.name  # nosec
        assert job.name == Job.compose_resource_name(
            parent_name=solver_or_program.resource_name,
            job_id=job.id,
        )
        return job, new_project

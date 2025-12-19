from celery import (  # type: ignore[import-untyped] # pylint: disable=no-name-in-module
    Task,
)
from celery_library.worker.app_server import get_app_server
from fastapi import FastAPI
from models_library.functions import RegisteredFunction, RegisteredFunctionJob
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from servicelib.celery.models import TaskKey

from simcore_service_api_server._service_function_jobs import FunctionJobService

from ....api.dependencies.authentication import Identity
from ....api.dependencies.rabbitmq import get_rabbitmq_rpc_client
from ....api.dependencies.services import (
    get_catalog_service,
    get_directorv2_service,
    get_function_job_service,
    get_function_service,
    get_job_service,
    get_solver_service,
    get_storage_service,
)
from ....api.dependencies.webserver_http import (
    get_session_cookie,
    get_webserver_session,
)
from ....api.dependencies.webserver_rpc import get_wb_api_rpc_client
from ....models.api_resources import JobLinks
from ....models.domain.functions import PreRegisteredFunctionJobData
from ....models.schemas.jobs import JobPricingSpecification
from ....services_http.director_v2 import DirectorV2Api
from ....services_http.storage import StorageApi


async def _assemble_function_job_service(
    *,
    app: FastAPI,
    user_identity: Identity,
) -> FunctionJobService:
    # This should ideally be done by a dependency injection system (like it is done in the api-server).
    # However, for that we would need to introduce a dependency injection system which is not coupled to,
    # but compatible with FastAPI's Depends. One suggestion: https://github.com/ets-labs/python-dependency-injector.
    # See also https://github.com/fastapi/fastapi/issues/1105#issuecomment-609919850.
    settings = app.state.settings
    assert settings.API_SERVER_WEBSERVER  # nosec
    session_cookie = get_session_cookie(
        identity=user_identity.email, settings=settings.API_SERVER_WEBSERVER, app=app
    )

    rpc_client = get_rabbitmq_rpc_client(app=app)
    web_server_rest_client = get_webserver_session(
        app=app, session_cookies=session_cookie, identity=user_identity
    )
    web_api_rpc_client = await get_wb_api_rpc_client(app=app)
    director2_api = DirectorV2Api.get_instance(app=app)
    assert isinstance(director2_api, DirectorV2Api)  # nosec
    storage_api = StorageApi.get_instance(app=app)
    assert isinstance(storage_api, StorageApi)  # nosec
    catalog_service = get_catalog_service(
        rpc_client=rpc_client,
        user_id=user_identity.user_id,
        product_name=user_identity.product_name,
    )

    storage_service = get_storage_service(
        rpc_client=rpc_client,
        user_id=user_identity.user_id,
        product_name=user_identity.product_name,
    )
    directorv2_service = get_directorv2_service(rpc_client=rpc_client)

    solver_service = get_solver_service(
        catalog_service=catalog_service,
        user_id=user_identity.user_id,
        product_name=user_identity.product_name,
    )

    function_service = get_function_service(
        web_rpc_api=web_api_rpc_client,
        user_id=user_identity.user_id,
        product_name=user_identity.product_name,
    )

    job_service = get_job_service(
        web_rest_api=web_server_rest_client,
        director2_api=director2_api,
        storage_api=storage_api,
        web_rpc_api=web_api_rpc_client,
        storage_service=storage_service,
        directorv2_service=directorv2_service,
        user_id=user_identity.user_id,
        product_name=user_identity.product_name,
        solver_service=solver_service,
    )

    return get_function_job_service(
        web_rpc_api=web_api_rpc_client,
        job_service=job_service,
        user_id=user_identity.user_id,
        product_name=user_identity.product_name,
        function_service=function_service,
        webserver_api=web_server_rest_client,
        storage_service=storage_service,
    )


async def run_function(
    task: Task,
    task_key: TaskKey,
    *,
    user_identity: Identity,
    function: RegisteredFunction,
    pre_registered_function_job_data: PreRegisteredFunctionJobData,
    pricing_spec: JobPricingSpecification | None,
    job_links: JobLinks,
    x_simcore_parent_project_uuid: ProjectID | None,
    x_simcore_parent_node_id: NodeID | None,
) -> RegisteredFunctionJob:
    assert task_key  # nosec
    app = get_app_server(task.app).app
    function_job_service = await _assemble_function_job_service(
        app=app, user_identity=user_identity
    )

    return await function_job_service.run_function(
        function=function,
        pre_registered_function_job_data=pre_registered_function_job_data,
        pricing_spec=pricing_spec,
        job_links=job_links,
        x_simcore_parent_project_uuid=x_simcore_parent_project_uuid,
        x_simcore_parent_node_id=x_simcore_parent_node_id,
    )

from aiohttp import web
from models_library.api_schemas_webserver import WEBSERVER_RPC_NAMESPACE
from models_library.api_schemas_webserver.functions_wb_schema import (
    Function,
    FunctionClass,
    FunctionClassSpecificData,
    FunctionDB,
    FunctionID,
    FunctionInputs,
    FunctionInputSchema,
    FunctionJob,
    FunctionJobClassSpecificData,
    FunctionJobDB,
    FunctionJobID,
    FunctionOutputSchema,
    ProjectFunction,
    ProjectFunctionJob,
)
from servicelib.rabbitmq import RPCRouter

from ..rabbitmq import get_rabbitmq_rpc_server
from . import _functions_repository

router = RPCRouter()


@router.expose()
async def ping(app: web.Application) -> str:
    assert app
    return "pong from webserver"


@router.expose()
async def register_function(app: web.Application, *, function: Function) -> Function:
    assert app
    if function.function_class == FunctionClass.project:
        saved_function = await _functions_repository.create_function(
            app=app,
            function=FunctionDB(
                title=function.title,
                description=function.description,
                input_schema=function.input_schema,
                output_schema=function.output_schema,
                function_class=function.function_class,
                class_specific_data=FunctionClassSpecificData(
                    {
                        "project_id": str(function.project_id),
                    }
                ),
            ),
        )
        return ProjectFunction(
            uid=saved_function.uuid,
            title=saved_function.title,
            description=saved_function.description,
            input_schema=saved_function.input_schema,
            output_schema=saved_function.output_schema,
            project_id=saved_function.class_specific_data["project_id"],
        )
    else:  # noqa: RET505
        msg = f"Unsupported function class: {function.function_class}"
        raise TypeError(msg)


def _decode_function(
    function: FunctionDB,
) -> Function:
    if function.function_class == "project":
        return ProjectFunction(
            uid=function.uuid,
            title=function.title,
            description=function.description,
            input_schema=function.input_schema,
            output_schema=function.output_schema,
            project_id=function.class_specific_data["project_id"],
        )
    else:  # noqa: RET505
        msg = f"Unsupported function class: [{function.function_class}]"
        raise TypeError(msg)


@router.expose()
async def get_function(app: web.Application, *, function_id: FunctionID) -> Function:
    assert app
    returned_function = await _functions_repository.get_function(
        app=app,
        function_id=function_id,
    )
    return _decode_function(
        returned_function,
    )


@router.expose()
async def get_function_job(
    app: web.Application, *, function_job_id: FunctionJobID
) -> FunctionJob:
    assert app
    returned_function_job = await _functions_repository.get_function_job(
        app=app,
        function_job_id=function_job_id,
    )
    assert returned_function_job is not None

    if returned_function_job.function_class == FunctionClass.project:
        return ProjectFunctionJob(
            uid=returned_function_job.uuid,
            title=returned_function_job.title,
            description="",
            function_uid=returned_function_job.function_uuid,
            inputs=returned_function_job.inputs,
            outputs=None,
            project_job_id=returned_function_job.class_specific_data["project_job_id"],
        )
    else:  # noqa: RET505
        msg = f"Unsupported function class: [{returned_function_job.function_class}]"
        raise TypeError(msg)


@router.expose()
async def list_function_jobs(app: web.Application) -> list[FunctionJob]:
    assert app
    returned_function_jobs = await _functions_repository.list_function_jobs(
        app=app,
    )
    return [
        ProjectFunctionJob(
            uid=returned_function_job.uuid,
            title=returned_function_job.title,
            description="",
            function_uid=returned_function_job.function_uuid,
            inputs=returned_function_job.inputs,
            outputs=None,
            project_job_id=returned_function_job.class_specific_data["project_job_id"],
        )
        for returned_function_job in returned_function_jobs
    ]


@router.expose()
async def get_function_input_schema(
    app: web.Application, *, function_id: FunctionID
) -> FunctionInputSchema:
    assert app
    returned_function = await _functions_repository.get_function(
        app=app,
        function_id=function_id,
    )
    return FunctionInputSchema(
        schema_dict=(
            returned_function.input_schema.schema_dict
            if returned_function.input_schema
            else None
        )
    )


@router.expose()
async def get_function_output_schema(
    app: web.Application, *, function_id: FunctionID
) -> FunctionOutputSchema:
    assert app
    returned_function = await _functions_repository.get_function(
        app=app,
        function_id=function_id,
    )
    return FunctionOutputSchema(
        schema_dict=(
            returned_function.output_schema.schema_dict
            if returned_function.output_schema
            else None
        )
    )


@router.expose()
async def list_functions(app: web.Application) -> list[Function]:
    assert app
    returned_functions = await _functions_repository.list_functions(
        app=app,
    )
    return [
        _decode_function(returned_function) for returned_function in returned_functions
    ]


@router.expose()
async def delete_function(app: web.Application, *, function_id: FunctionID) -> None:
    assert app
    await _functions_repository.delete_function(
        app=app,
        function_id=function_id,
    )


@router.expose()
async def register_function_job(
    app: web.Application, *, function_job: FunctionJob
) -> FunctionJob:
    assert app
    if function_job.function_class == FunctionClass.project:
        created_function_job_db = await _functions_repository.register_function_job(
            app=app,
            function_job=FunctionJobDB(
                title=function_job.title,
                function_uuid=function_job.function_uid,
                inputs=function_job.inputs,
                outputs=None,
                class_specific_data=FunctionJobClassSpecificData(
                    {
                        "project_job_id": str(function_job.project_job_id),
                    }
                ),
                function_class=function_job.function_class,
            ),
        )

        return ProjectFunctionJob(
            uid=created_function_job_db.uuid,
            title=created_function_job_db.title,
            description="",
            function_uid=created_function_job_db.function_uuid,
            inputs=created_function_job_db.inputs,
            outputs=None,
            project_job_id=created_function_job_db.class_specific_data[
                "project_job_id"
            ],
        )
    else:  # noqa: RET505
        msg = f"Unsupported function class: [{function_job.function_class}]"
        raise TypeError(msg)


@router.expose()
async def find_cached_function_job(
    app: web.Application, *, function_id: FunctionID, inputs: FunctionInputs
) -> FunctionJob | None:
    assert app
    returned_function_job = await _functions_repository.find_cached_function_job(
        app=app, function_id=function_id, inputs=inputs
    )
    if returned_function_job is None:
        return None

    if returned_function_job.function_class == FunctionClass.project:
        return ProjectFunctionJob(
            uid=returned_function_job.uuid,
            title=returned_function_job.title,
            description="",
            function_uid=returned_function_job.function_uuid,
            inputs=returned_function_job.inputs,
            outputs=None,
            project_job_id=returned_function_job.class_specific_data["project_job_id"],
        )
    else:  # noqa: RET505
        msg = f"Unsupported function class: [{returned_function_job.function_class}]"
        raise TypeError(msg)


async def register_rpc_routes_on_startup(app: web.Application):
    rpc_server = get_rabbitmq_rpc_server(app)
    await rpc_server.register_router(router, WEBSERVER_RPC_NAMESPACE, app)

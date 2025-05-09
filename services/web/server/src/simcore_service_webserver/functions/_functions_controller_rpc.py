from aiohttp import web
from models_library.api_schemas_webserver import WEBSERVER_RPC_NAMESPACE
from models_library.api_schemas_webserver.functions_wb_schema import (
    Function,
    FunctionClass,
    FunctionClassSpecificData,
    FunctionDB,
    FunctionID,
    FunctionIDNotFoundError,
    FunctionInputs,
    FunctionInputSchema,
    FunctionJob,
    FunctionJobClassSpecificData,
    FunctionJobCollection,
    FunctionJobCollectionIDNotFoundError,
    FunctionJobDB,
    FunctionJobID,
    FunctionJobIDNotFoundError,
    FunctionOutputSchema,
    ProjectFunction,
    ProjectFunctionJob,
    RegisterFunctionJobCollectionWithIDError,
    RegisterFunctionJobWithIDError,
    RegisterFunctionWithIDError,
    SolverFunction,
    SolverFunctionJob,
    UnsupportedFunctionClassError,
    UnsupportedFunctionJobClassError,
)
from models_library.rest_pagination import PageMetaInfoLimitOffset
from servicelib.rabbitmq import RPCRouter

from ..rabbitmq import get_rabbitmq_rpc_server
from . import _functions_repository

router = RPCRouter()

# pylint: disable=no-else-return


@router.expose(
    reraise_if_error_type=(UnsupportedFunctionClassError, RegisterFunctionWithIDError)
)
async def register_function(app: web.Application, *, function: Function) -> Function:
    assert app
    saved_function = await _functions_repository.register_function(
        app=app, function=_encode_function(function)
    )
    return _decode_function(saved_function)


@router.expose(
    reraise_if_error_type=(
        UnsupportedFunctionJobClassError,
        RegisterFunctionJobWithIDError,
    )
)
async def register_function_job(
    app: web.Application, *, function_job: FunctionJob
) -> FunctionJob:
    assert app
    created_function_job_db = await _functions_repository.register_function_job(
        app=app, function_job=_encode_functionjob(function_job)
    )
    return _decode_functionjob(created_function_job_db)


@router.expose(reraise_if_error_type=(RegisterFunctionJobCollectionWithIDError,))
async def register_function_job_collection(
    app: web.Application, *, function_job_collection: FunctionJobCollection
) -> FunctionJobCollection:
    assert app
    registered_function_job_collection, registered_job_ids = (
        await _functions_repository.register_function_job_collection(
            app=app,
            function_job_collection=function_job_collection,
        )
    )
    return FunctionJobCollection(
        uid=registered_function_job_collection.uuid,
        title=registered_function_job_collection.title,
        description=registered_function_job_collection.description,
        job_ids=registered_job_ids,
    )


@router.expose(reraise_if_error_type=(FunctionIDNotFoundError,))
async def get_function(app: web.Application, *, function_id: FunctionID) -> Function:
    assert app
    returned_function = await _functions_repository.get_function(
        app=app,
        function_id=function_id,
    )
    return _decode_function(
        returned_function,
    )


@router.expose(reraise_if_error_type=(FunctionJobIDNotFoundError,))
async def get_function_job(
    app: web.Application, *, function_job_id: FunctionJobID
) -> FunctionJob:
    assert app
    returned_function_job = await _functions_repository.get_function_job(
        app=app,
        function_job_id=function_job_id,
    )
    assert returned_function_job is not None

    return _decode_functionjob(returned_function_job)


@router.expose(reraise_if_error_type=(FunctionJobCollectionIDNotFoundError,))
async def get_function_job_collection(
    app: web.Application, *, function_job_collection_id: FunctionJobID
) -> FunctionJobCollection:
    assert app
    returned_function_job_collection, returned_job_ids = (
        await _functions_repository.get_function_job_collection(
            app=app,
            function_job_collection_id=function_job_collection_id,
        )
    )
    return FunctionJobCollection(
        uid=returned_function_job_collection.uuid,
        title=returned_function_job_collection.title,
        description=returned_function_job_collection.description,
        job_ids=returned_job_ids,
    )


@router.expose()
async def list_functions(
    app: web.Application,
    pagination_limit: int,
    pagination_offset: int,
) -> tuple[list[Function], PageMetaInfoLimitOffset]:
    assert app
    returned_functions, page = await _functions_repository.list_functions(
        app=app,
        pagination_limit=pagination_limit,
        pagination_offset=pagination_offset,
    )
    return [
        _decode_function(returned_function) for returned_function in returned_functions
    ], page


@router.expose()
async def list_function_jobs(
    app: web.Application,
    pagination_limit: int,
    pagination_offset: int,
) -> tuple[list[FunctionJob], PageMetaInfoLimitOffset]:
    assert app
    returned_function_jobs, page = await _functions_repository.list_function_jobs(
        app=app,
        pagination_limit=pagination_limit,
        pagination_offset=pagination_offset,
    )
    return [
        _decode_functionjob(returned_function_job)
        for returned_function_job in returned_function_jobs
    ], page


@router.expose()
async def list_function_job_collections(
    app: web.Application,
    pagination_limit: int,
    pagination_offset: int,
) -> tuple[list[FunctionJobCollection], PageMetaInfoLimitOffset]:
    assert app
    returned_function_job_collections, page = (
        await _functions_repository.list_function_job_collections(
            app=app,
            pagination_limit=pagination_limit,
            pagination_offset=pagination_offset,
        )
    )
    return [
        FunctionJobCollection(
            uid=function_job_collection.uuid,
            title=function_job_collection.title,
            description=function_job_collection.description,
            job_ids=job_ids,
        )
        for function_job_collection, job_ids in returned_function_job_collections
    ], page


@router.expose(reraise_if_error_type=(FunctionIDNotFoundError,))
async def delete_function(app: web.Application, *, function_id: FunctionID) -> None:
    assert app
    await _functions_repository.delete_function(
        app=app,
        function_id=function_id,
    )


@router.expose(reraise_if_error_type=(FunctionJobIDNotFoundError,))
async def delete_function_job(
    app: web.Application, *, function_job_id: FunctionJobID
) -> None:
    assert app
    await _functions_repository.delete_function_job(
        app=app,
        function_job_id=function_job_id,
    )


@router.expose(reraise_if_error_type=(FunctionJobCollectionIDNotFoundError,))
async def delete_function_job_collection(
    app: web.Application, *, function_job_collection_id: FunctionJobID
) -> None:
    assert app
    await _functions_repository.delete_function_job_collection(
        app=app,
        function_job_collection_id=function_job_collection_id,
    )


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
    elif returned_function_job.function_class == FunctionClass.solver:  # noqa: RET505
        return SolverFunctionJob(
            uid=returned_function_job.uuid,
            title=returned_function_job.title,
            description="",
            function_uid=returned_function_job.function_uuid,
            inputs=returned_function_job.inputs,
            outputs=None,
            solver_job_id=returned_function_job.class_specific_data["solver_job_id"],
        )
    else:
        raise UnsupportedFunctionJobClassError(
            function_job_class=returned_function_job.function_class
        )


@router.expose(reraise_if_error_type=(FunctionIDNotFoundError,))
async def get_function_input_schema(
    app: web.Application, *, function_id: FunctionID
) -> FunctionInputSchema:
    assert app
    returned_function = await _functions_repository.get_function(
        app=app,
        function_id=function_id,
    )
    return _decode_function(returned_function).input_schema


@router.expose(reraise_if_error_type=(FunctionIDNotFoundError,))
async def get_function_output_schema(
    app: web.Application, *, function_id: FunctionID
) -> FunctionOutputSchema:
    assert app
    returned_function = await _functions_repository.get_function(
        app=app,
        function_id=function_id,
    )
    return _decode_function(returned_function).output_schema


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
            default_inputs=function.default_inputs,
        )
    elif function.function_class == "solver":  # noqa: RET505
        return SolverFunction(
            uid=function.uuid,
            title=function.title,
            description=function.description,
            input_schema=function.input_schema,
            output_schema=function.output_schema,
            solver_key=function.class_specific_data["solver_key"],
            solver_version=function.class_specific_data["solver_version"],
            default_inputs=function.default_inputs,
        )
    else:
        raise UnsupportedFunctionClassError(function_class=function.function_class)


def _encode_function(
    function: Function,
) -> FunctionDB:
    if function.function_class == FunctionClass.project:
        class_specific_data = FunctionClassSpecificData(
            {"project_id": str(function.project_id)}
        )
    elif function.function_class == FunctionClass.solver:
        class_specific_data = FunctionClassSpecificData(
            {
                "solver_key": str(function.solver_key),
                "solver_version": str(function.solver_version),
            }
        )
    else:
        raise UnsupportedFunctionClassError(function_class=function.function_class)

    return FunctionDB(
        uuid=function.uid,
        title=function.title,
        description=function.description,
        input_schema=function.input_schema,
        output_schema=function.output_schema,
        function_class=function.function_class,
        default_inputs=function.default_inputs,
        class_specific_data=class_specific_data,
    )


def _encode_functionjob(
    functionjob: FunctionJob,
) -> FunctionJobDB:
    if functionjob.function_class == FunctionClass.project:
        return FunctionJobDB(
            uuid=functionjob.uid,
            title=functionjob.title,
            function_uuid=functionjob.function_uid,
            inputs=functionjob.inputs,
            outputs=functionjob.outputs,
            class_specific_data=FunctionJobClassSpecificData(
                {
                    "project_job_id": str(functionjob.project_job_id),
                }
            ),
            function_class=functionjob.function_class,
        )
    elif functionjob.function_class == FunctionClass.solver:  # noqa: RET505
        return FunctionJobDB(
            uuid=functionjob.uid,
            title=functionjob.title,
            function_uuid=functionjob.function_uid,
            inputs=functionjob.inputs,
            outputs=functionjob.outputs,
            class_specific_data=FunctionJobClassSpecificData(
                {
                    "solver_job_id": str(functionjob.solver_job_id),
                }
            ),
            function_class=functionjob.function_class,
        )
    else:
        raise UnsupportedFunctionJobClassError(
            function_job_class=functionjob.function_class
        )


def _decode_functionjob(
    functionjob_db: FunctionJobDB,
) -> FunctionJob:
    if functionjob_db.function_class == FunctionClass.project:
        return ProjectFunctionJob(
            uid=functionjob_db.uuid,
            title=functionjob_db.title,
            description="",
            function_uid=functionjob_db.function_uuid,
            inputs=functionjob_db.inputs,
            outputs=functionjob_db.outputs,
            project_job_id=functionjob_db.class_specific_data["project_job_id"],
        )
    elif functionjob_db.function_class == FunctionClass.solver:  # noqa: RET505
        return SolverFunctionJob(
            uid=functionjob_db.uuid,
            title=functionjob_db.title,
            description="",
            function_uid=functionjob_db.function_uuid,
            inputs=functionjob_db.inputs,
            outputs=functionjob_db.outputs,
            solver_job_id=functionjob_db.class_specific_data["solver_job_id"],
        )
    else:
        raise UnsupportedFunctionJobClassError(
            function_job_class=functionjob_db.function_class
        )


async def register_rpc_routes_on_startup(app: web.Application):
    rpc_server = get_rabbitmq_rpc_server(app)
    await rpc_server.register_router(router, WEBSERVER_RPC_NAMESPACE, app)

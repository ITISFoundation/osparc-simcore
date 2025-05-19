from aiohttp import web
from models_library.functions import (
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
    RegisteredFunction,
    RegisteredFunctionDB,
    RegisteredFunctionJob,
    RegisteredFunctionJobCollection,
    RegisteredFunctionJobDB,
    RegisteredProjectFunction,
    RegisteredProjectFunctionJob,
    RegisteredSolverFunction,
    RegisteredSolverFunctionJob,
    UnsupportedFunctionClassError,
    UnsupportedFunctionJobClassError,
)
from models_library.rest_pagination import PageMetaInfoLimitOffset
from servicelib.rabbitmq import RPCRouter

from . import _functions_repository

router = RPCRouter()

# pylint: disable=no-else-return


@router.expose(reraise_if_error_type=(UnsupportedFunctionClassError,))
async def register_function(
    app: web.Application, *, function: Function
) -> RegisteredFunction:
    encoded_function = _encode_function(function)
    saved_function = await _functions_repository.create_function(
        app=app,
        title=encoded_function.title,
        function_class=encoded_function.function_class,
        description=encoded_function.description,
        input_schema=encoded_function.input_schema,
        output_schema=encoded_function.output_schema,
        default_inputs=encoded_function.default_inputs,
        class_specific_data=encoded_function.class_specific_data,
    )
    return _decode_function(saved_function)


@router.expose(reraise_if_error_type=(UnsupportedFunctionJobClassError,))
async def register_function_job(
    app: web.Application, *, function_job: FunctionJob
) -> RegisteredFunctionJob:
    encoded_function_job = _encode_functionjob(function_job)
    created_function_job_db = await _functions_repository.create_function_job(
        app=app,
        function_class=encoded_function_job.function_class,
        title=encoded_function_job.title,
        description=encoded_function_job.description,
        function_uid=encoded_function_job.function_uuid,
        inputs=encoded_function_job.inputs,
        outputs=encoded_function_job.outputs,
        class_specific_data=encoded_function_job.class_specific_data,
    )
    return _decode_functionjob(created_function_job_db)


@router.expose(reraise_if_error_type=())
async def register_function_job_collection(
    app: web.Application, *, function_job_collection: FunctionJobCollection
) -> RegisteredFunctionJobCollection:
    registered_function_job_collection, registered_job_ids = (
        await _functions_repository.create_function_job_collection(
            app=app,
            title=function_job_collection.title,
            description=function_job_collection.description,
            job_ids=function_job_collection.job_ids,
        )
    )
    return RegisteredFunctionJobCollection(
        uid=registered_function_job_collection.uuid,
        title=registered_function_job_collection.title,
        description=registered_function_job_collection.description,
        job_ids=registered_job_ids,
    )


@router.expose(reraise_if_error_type=(FunctionIDNotFoundError,))
async def get_function(
    app: web.Application, *, function_id: FunctionID
) -> RegisteredFunction:
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
) -> RegisteredFunctionJob:
    returned_function_job = await _functions_repository.get_function_job(
        app=app,
        function_job_id=function_job_id,
    )
    assert returned_function_job is not None

    return _decode_functionjob(returned_function_job)


@router.expose(reraise_if_error_type=(FunctionJobCollectionIDNotFoundError,))
async def get_function_job_collection(
    app: web.Application, *, function_job_collection_id: FunctionJobID
) -> RegisteredFunctionJobCollection:
    returned_function_job_collection, returned_job_ids = (
        await _functions_repository.get_function_job_collection(
            app=app,
            function_job_collection_id=function_job_collection_id,
        )
    )
    return RegisteredFunctionJobCollection(
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
) -> tuple[list[RegisteredFunction], PageMetaInfoLimitOffset]:
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
    filter_by_function_id: FunctionID | None = None,
) -> tuple[list[RegisteredFunctionJob], PageMetaInfoLimitOffset]:
    returned_function_jobs, page = await _functions_repository.list_function_jobs(
        app=app,
        pagination_limit=pagination_limit,
        pagination_offset=pagination_offset,
        filter_by_function_id=filter_by_function_id,
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
) -> tuple[list[RegisteredFunctionJobCollection], PageMetaInfoLimitOffset]:
    returned_function_job_collections, page = (
        await _functions_repository.list_function_job_collections(
            app=app,
            pagination_limit=pagination_limit,
            pagination_offset=pagination_offset,
        )
    )
    return [
        RegisteredFunctionJobCollection(
            uid=function_job_collection.uuid,
            title=function_job_collection.title,
            description=function_job_collection.description,
            job_ids=job_ids,
        )
        for function_job_collection, job_ids in returned_function_job_collections
    ], page


@router.expose(reraise_if_error_type=(FunctionIDNotFoundError,))
async def delete_function(app: web.Application, *, function_id: FunctionID) -> None:
    await _functions_repository.delete_function(
        app=app,
        function_id=function_id,
    )


@router.expose(reraise_if_error_type=(FunctionJobIDNotFoundError,))
async def delete_function_job(
    app: web.Application, *, function_job_id: FunctionJobID
) -> None:
    await _functions_repository.delete_function_job(
        app=app,
        function_job_id=function_job_id,
    )


@router.expose(reraise_if_error_type=(FunctionJobCollectionIDNotFoundError,))
async def delete_function_job_collection(
    app: web.Application, *, function_job_collection_id: FunctionJobID
) -> None:
    await _functions_repository.delete_function_job_collection(
        app=app,
        function_job_collection_id=function_job_collection_id,
    )


@router.expose()
async def update_function_title(
    app: web.Application, *, function_id: FunctionID, title: str
) -> RegisteredFunction:
    updated_function = await _functions_repository.update_function_title(
        app=app,
        function_id=function_id,
        title=title,
    )
    return _decode_function(updated_function)


@router.expose(reraise_if_error_type=(FunctionIDNotFoundError,))
async def update_function_description(
    app: web.Application, *, function_id: FunctionID, description: str
) -> RegisteredFunction:
    updated_function = await _functions_repository.update_function_description(
        app=app,
        function_id=function_id,
        description=description,
    )
    return _decode_function(updated_function)


@router.expose()
async def find_cached_function_job(
    app: web.Application, *, function_id: FunctionID, inputs: FunctionInputs
) -> FunctionJob | None:
    returned_function_job = await _functions_repository.find_cached_function_job(
        app=app, function_id=function_id, inputs=inputs
    )
    if returned_function_job is None:
        return None

    if returned_function_job.function_class == FunctionClass.PROJECT:
        return RegisteredProjectFunctionJob(
            uid=returned_function_job.uuid,
            title=returned_function_job.title,
            description=returned_function_job.description,
            function_uid=returned_function_job.function_uuid,
            inputs=returned_function_job.inputs,
            outputs=None,
            project_job_id=returned_function_job.class_specific_data["project_job_id"],
        )
    if returned_function_job.function_class == FunctionClass.SOLVER:
        return RegisteredSolverFunctionJob(
            uid=returned_function_job.uuid,
            title=returned_function_job.title,
            description=returned_function_job.description,
            function_uid=returned_function_job.function_uuid,
            inputs=returned_function_job.inputs,
            outputs=None,
            solver_job_id=returned_function_job.class_specific_data["solver_job_id"],
        )

    raise UnsupportedFunctionJobClassError(
        function_job_class=returned_function_job.function_class
    )


@router.expose(reraise_if_error_type=(FunctionIDNotFoundError,))
async def get_function_input_schema(
    app: web.Application, *, function_id: FunctionID
) -> FunctionInputSchema:
    returned_function = await _functions_repository.get_function(
        app=app,
        function_id=function_id,
    )
    return _decode_function(returned_function).input_schema


@router.expose(reraise_if_error_type=(FunctionIDNotFoundError,))
async def get_function_output_schema(
    app: web.Application, *, function_id: FunctionID
) -> FunctionOutputSchema:
    returned_function = await _functions_repository.get_function(
        app=app,
        function_id=function_id,
    )
    return _decode_function(returned_function).output_schema


def _decode_function(
    function: RegisteredFunctionDB,
) -> RegisteredFunction:
    if function.function_class == FunctionClass.PROJECT:
        return RegisteredProjectFunction(
            uid=function.uuid,
            title=function.title,
            description=function.description,
            input_schema=function.input_schema,
            output_schema=function.output_schema,
            project_id=function.class_specific_data["project_id"],
            default_inputs=function.default_inputs,
        )

    if function.function_class == FunctionClass.SOLVER:
        return RegisteredSolverFunction(
            uid=function.uuid,
            title=function.title,
            description=function.description,
            input_schema=function.input_schema,
            output_schema=function.output_schema,
            solver_key=function.class_specific_data["solver_key"],
            solver_version=function.class_specific_data["solver_version"],
            default_inputs=function.default_inputs,
        )

    raise UnsupportedFunctionClassError(function_class=function.function_class)


def _encode_function(
    function: Function,
) -> FunctionDB:
    if function.function_class == FunctionClass.PROJECT:
        class_specific_data = FunctionClassSpecificData(
            {"project_id": str(function.project_id)}
        )
    elif function.function_class == FunctionClass.SOLVER:
        class_specific_data = FunctionClassSpecificData(
            {
                "solver_key": str(function.solver_key),
                "solver_version": str(function.solver_version),
            }
        )
    else:
        raise UnsupportedFunctionClassError(function_class=function.function_class)

    return FunctionDB(
        title=function.title,
        description=function.description,
        input_schema=function.input_schema,
        output_schema=function.output_schema,
        default_inputs=function.default_inputs,
        class_specific_data=class_specific_data,
        function_class=function.function_class,
    )


def _encode_functionjob(
    functionjob: FunctionJob,
) -> FunctionJobDB:

    if functionjob.function_class == FunctionClass.PROJECT:
        class_specific_data = FunctionJobClassSpecificData(
            {
                "project_job_id": str(functionjob.project_job_id),
            }
        )
    elif functionjob.function_class == FunctionClass.SOLVER:
        class_specific_data = FunctionJobClassSpecificData(
            {
                "solver_job_id": str(functionjob.solver_job_id),
            }
        )
    else:
        raise UnsupportedFunctionJobClassError(
            function_job_class=functionjob.function_class
        )

    return FunctionJobDB(
        title=functionjob.title,
        function_uuid=functionjob.function_uid,
        inputs=functionjob.inputs,
        outputs=functionjob.outputs,
        class_specific_data=class_specific_data,
        function_class=functionjob.function_class,
    )


def _decode_functionjob(
    functionjob_db: RegisteredFunctionJobDB,
) -> RegisteredFunctionJob:
    if functionjob_db.function_class == FunctionClass.PROJECT:
        return RegisteredProjectFunctionJob(
            uid=functionjob_db.uuid,
            title=functionjob_db.title,
            description="",
            function_uid=functionjob_db.function_uuid,
            inputs=functionjob_db.inputs,
            outputs=functionjob_db.outputs,
            project_job_id=functionjob_db.class_specific_data["project_job_id"],
        )

    if functionjob_db.function_class == FunctionClass.SOLVER:
        return RegisteredSolverFunctionJob(
            uid=functionjob_db.uuid,
            title=functionjob_db.title,
            description="",
            function_uid=functionjob_db.function_uuid,
            inputs=functionjob_db.inputs,
            outputs=functionjob_db.outputs,
            solver_job_id=functionjob_db.class_specific_data["solver_job_id"],
        )

    raise UnsupportedFunctionJobClassError(
        function_job_class=functionjob_db.function_class
    )

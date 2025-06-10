from aiohttp import web
from models_library.functions import (
    Function,
    FunctionClass,
    FunctionClassSpecificData,
    FunctionDB,
    FunctionID,
    FunctionInputs,
    FunctionInputSchema,
    FunctionJob,
    FunctionJobClassSpecificData,
    FunctionJobCollection,
    FunctionJobCollectionsListFilters,
    FunctionJobDB,
    FunctionJobID,
    FunctionOutputSchema,
    FunctionUserAbilities,
    FunctionUserAccessRights,
    RegisteredFunction,
    RegisteredFunctionDB,
    RegisteredFunctionJob,
    RegisteredFunctionJobCollection,
    RegisteredFunctionJobDB,
    RegisteredProjectFunction,
    RegisteredProjectFunctionJob,
    RegisteredSolverFunction,
    RegisteredSolverFunctionJob,
)
from models_library.functions_errors import (
    UnsupportedFunctionClassError,
    UnsupportedFunctionJobClassError,
)
from models_library.products import ProductName
from models_library.rest_pagination import PageMetaInfoLimitOffset
from models_library.users import UserID
from servicelib.rabbitmq import RPCRouter

from . import _functions_repository

router = RPCRouter()


async def register_function(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: ProductName,
    function: Function,
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
        user_id=user_id,
        product_name=product_name,
    )
    return _decode_function(saved_function)


async def register_function_job(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: ProductName,
    function_job: FunctionJob,
) -> RegisteredFunctionJob:
    encoded_function_job = _encode_functionjob(function_job)
    created_function_job_db = await _functions_repository.create_function_job(
        app=app,
        user_id=user_id,
        product_name=product_name,
        function_class=encoded_function_job.function_class,
        title=encoded_function_job.title,
        description=encoded_function_job.description,
        function_uid=encoded_function_job.function_uuid,
        inputs=encoded_function_job.inputs,
        outputs=encoded_function_job.outputs,
        class_specific_data=encoded_function_job.class_specific_data,
    )
    return _decode_functionjob(created_function_job_db)


async def register_function_job_collection(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: ProductName,
    function_job_collection: FunctionJobCollection,
) -> RegisteredFunctionJobCollection:
    registered_function_job_collection, registered_job_ids = (
        await _functions_repository.create_function_job_collection(
            app=app,
            user_id=user_id,
            product_name=product_name,
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
        created_at=registered_function_job_collection.created,
    )


async def get_function(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: ProductName,
    function_id: FunctionID,
) -> RegisteredFunction:
    returned_function = await _functions_repository.get_function(
        app=app,
        user_id=user_id,
        product_name=product_name,
        function_id=function_id,
    )
    return _decode_function(
        returned_function,
    )


async def get_function_job(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: ProductName,
    function_job_id: FunctionJobID,
) -> RegisteredFunctionJob:
    returned_function_job = await _functions_repository.get_function_job(
        app=app,
        user_id=user_id,
        product_name=product_name,
        function_job_id=function_job_id,
    )
    assert returned_function_job is not None

    return _decode_functionjob(returned_function_job)


async def get_function_job_collection(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: ProductName,
    function_job_collection_id: FunctionJobID,
) -> RegisteredFunctionJobCollection:
    returned_function_job_collection, returned_job_ids = (
        await _functions_repository.get_function_job_collection(
            app=app,
            user_id=user_id,
            product_name=product_name,
            function_job_collection_id=function_job_collection_id,
        )
    )
    return RegisteredFunctionJobCollection(
        uid=returned_function_job_collection.uuid,
        title=returned_function_job_collection.title,
        description=returned_function_job_collection.description,
        job_ids=returned_job_ids,
        created_at=returned_function_job_collection.created,
    )


async def list_functions(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: ProductName,
    pagination_limit: int,
    pagination_offset: int,
) -> tuple[list[RegisteredFunction], PageMetaInfoLimitOffset]:
    returned_functions, page = await _functions_repository.list_functions(
        app=app,
        user_id=user_id,
        product_name=product_name,
        pagination_limit=pagination_limit,
        pagination_offset=pagination_offset,
    )
    return [
        _decode_function(returned_function) for returned_function in returned_functions
    ], page


async def list_function_jobs(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: ProductName,
    pagination_limit: int,
    pagination_offset: int,
    filter_by_function_id: FunctionID | None = None,
) -> tuple[list[RegisteredFunctionJob], PageMetaInfoLimitOffset]:
    returned_function_jobs, page = await _functions_repository.list_function_jobs(
        app=app,
        user_id=user_id,
        product_name=product_name,
        pagination_limit=pagination_limit,
        pagination_offset=pagination_offset,
        filter_by_function_id=filter_by_function_id,
    )
    return [
        _decode_functionjob(returned_function_job)
        for returned_function_job in returned_function_jobs
    ], page


async def list_function_job_collections(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: ProductName,
    pagination_limit: int,
    pagination_offset: int,
    filters: FunctionJobCollectionsListFilters | None = None,
) -> tuple[list[RegisteredFunctionJobCollection], PageMetaInfoLimitOffset]:
    returned_function_job_collections, page = (
        await _functions_repository.list_function_job_collections(
            app=app,
            user_id=user_id,
            product_name=product_name,
            pagination_limit=pagination_limit,
            pagination_offset=pagination_offset,
            filters=filters,
        )
    )
    return [
        RegisteredFunctionJobCollection(
            uid=function_job_collection.uuid,
            title=function_job_collection.title,
            description=function_job_collection.description,
            job_ids=job_ids,
            created_at=function_job_collection.created,
        )
        for function_job_collection, job_ids in returned_function_job_collections
    ], page


async def delete_function(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: ProductName,
    function_id: FunctionID,
) -> None:
    await _functions_repository.delete_function(
        app=app,
        user_id=user_id,
        product_name=product_name,
        function_id=function_id,
    )


async def delete_function_job(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: ProductName,
    function_job_id: FunctionJobID,
) -> None:
    await _functions_repository.delete_function_job(
        app=app,
        user_id=user_id,
        product_name=product_name,
        function_job_id=function_job_id,
    )


async def delete_function_job_collection(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: ProductName,
    function_job_collection_id: FunctionJobID,
) -> None:
    await _functions_repository.delete_function_job_collection(
        app=app,
        user_id=user_id,
        product_name=product_name,
        function_job_collection_id=function_job_collection_id,
    )


async def update_function_title(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: ProductName,
    function_id: FunctionID,
    title: str,
) -> RegisteredFunction:
    updated_function = await _functions_repository.update_function_title(
        app=app,
        user_id=user_id,
        product_name=product_name,
        function_id=function_id,
        title=title,
    )
    return _decode_function(updated_function)


async def update_function_description(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: ProductName,
    function_id: FunctionID,
    description: str,
) -> RegisteredFunction:
    updated_function = await _functions_repository.update_function_description(
        app=app,
        user_id=user_id,
        product_name=product_name,
        function_id=function_id,
        description=description,
    )
    return _decode_function(updated_function)


async def find_cached_function_jobs(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: ProductName,
    function_id: FunctionID,
    inputs: FunctionInputs,
) -> list[RegisteredFunctionJob] | None:
    returned_function_jobs = await _functions_repository.find_cached_function_jobs(
        app=app,
        user_id=user_id,
        product_name=product_name,
        function_id=function_id,
        inputs=inputs,
    )
    if returned_function_jobs is None or len(returned_function_jobs) == 0:
        return None

    to_return_function_jobs: list[RegisteredFunctionJob] = []
    for returned_function_job in returned_function_jobs:
        if returned_function_job.function_class == FunctionClass.PROJECT:
            to_return_function_jobs.append(
                RegisteredProjectFunctionJob(
                    uid=returned_function_job.uuid,
                    title=returned_function_job.title,
                    description=returned_function_job.description,
                    function_uid=returned_function_job.function_uuid,
                    inputs=returned_function_job.inputs,
                    outputs=None,
                    project_job_id=returned_function_job.class_specific_data[
                        "project_job_id"
                    ],
                    created_at=returned_function_job.created,
                )
            )
        elif returned_function_job.function_class == FunctionClass.SOLVER:
            to_return_function_jobs.append(
                RegisteredSolverFunctionJob(
                    uid=returned_function_job.uuid,
                    title=returned_function_job.title,
                    description=returned_function_job.description,
                    function_uid=returned_function_job.function_uuid,
                    inputs=returned_function_job.inputs,
                    outputs=None,
                    solver_job_id=returned_function_job.class_specific_data[
                        "solver_job_id"
                    ],
                    created_at=returned_function_job.created,
                )
            )
        else:
            raise UnsupportedFunctionJobClassError(
                function_job_class=returned_function_job.function_class
            )

    return to_return_function_jobs


async def get_function_input_schema(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: ProductName,
    function_id: FunctionID,
) -> FunctionInputSchema:
    returned_function = await _functions_repository.get_function(
        app=app,
        user_id=user_id,
        product_name=product_name,
        function_id=function_id,
    )
    return _decode_function(returned_function).input_schema


async def get_function_output_schema(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: ProductName,
    function_id: FunctionID,
) -> FunctionOutputSchema:
    returned_function = await _functions_repository.get_function(
        app=app,
        user_id=user_id,
        product_name=product_name,
        function_id=function_id,
    )
    return _decode_function(returned_function).output_schema


async def get_function_user_permissions(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: ProductName,
    function_id: FunctionID,
) -> FunctionUserAccessRights:
    user_permissions = await _functions_repository.get_user_permissions(
        app=app,
        user_id=user_id,
        product_name=product_name,
        object_id=function_id,
        object_type="function",
    )
    return (
        FunctionUserAccessRights(
            user_id=user_id,
            read=user_permissions.read,
            write=user_permissions.write,
            execute=user_permissions.execute,
        )
        if user_permissions
        else FunctionUserAccessRights(
            user_id=user_id,
            read=False,
            write=False,
            execute=False,
        )
    )


async def get_functions_user_abilities(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: ProductName,
) -> FunctionUserAbilities:
    return await _functions_repository.get_user_abilities(
        app=app,
        user_id=user_id,
        product_name=product_name,
    )


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
            created_at=function.created,
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
            created_at=function.created,
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
            created_at=functionjob_db.created,
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
            created_at=functionjob_db.created,
        )

    raise UnsupportedFunctionJobClassError(
        function_job_class=functionjob_db.function_class
    )

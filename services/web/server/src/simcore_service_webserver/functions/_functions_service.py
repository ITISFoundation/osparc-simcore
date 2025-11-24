from typing import Literal

from aiohttp import web
from models_library.basic_types import IDStr
from models_library.functions import (
    BatchCreateRegisteredFunctionJobs,
    BatchUpdateRegisteredFunctionJobs,
    Function,
    FunctionClass,
    FunctionClassSpecificData,
    FunctionDB,
    FunctionGroupAccessRights,
    FunctionID,
    FunctionInputSchema,
    FunctionInputsList,
    FunctionJob,
    FunctionJobClassSpecificData,
    FunctionJobCollection,
    FunctionJobCollectionID,
    FunctionJobCollectionsListFilters,
    FunctionJobDB,
    FunctionJobID,
    FunctionJobList,
    FunctionJobPatchRequest,
    FunctionJobPatchRequestList,
    FunctionJobStatus,
    FunctionOutputs,
    FunctionOutputSchema,
    FunctionUpdate,
    FunctionUserAccessRights,
    FunctionUserApiAccessRights,
    RegisteredFunction,
    RegisteredFunctionDB,
    RegisteredFunctionJob,
    RegisteredFunctionJobCollection,
    RegisteredFunctionJobDB,
    RegisteredFunctionJobWithStatus,
    RegisteredFunctionJobWithStatusDB,
    RegisteredProjectFunction,
    RegisteredProjectFunctionJob,
    RegisteredProjectFunctionJobWithStatus,
    RegisteredSolverFunction,
    RegisteredSolverFunctionJob,
    RegisteredSolverFunctionJobWithStatus,
)
from models_library.functions_errors import (
    UnsupportedFunctionClassError,
    UnsupportedFunctionJobClassError,
)
from models_library.groups import GroupID
from models_library.products import ProductName
from models_library.rest_ordering import OrderBy
from models_library.rest_pagination import PageMetaInfoLimitOffset
from models_library.users import UserID
from pydantic import TypeAdapter
from servicelib.rabbitmq import RPCRouter

from . import (
    _function_job_collections_repository,
    _function_jobs_repository,
    _functions_permissions_repository,
    _functions_repository,
)
from ._functions_exceptions import FunctionGroupAccessRightsNotFoundError

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
    encoded_function_jobs = _encode_functionjob(function_job)
    created_function_jobs_db = await _function_jobs_repository.create_function_jobs(
        app=app,
        user_id=user_id,
        product_name=product_name,
        function_jobs=[encoded_function_jobs],
    )
    created_items = created_function_jobs_db.created_items
    assert len(created_items) == 1  # nosec
    return _decode_functionjob(created_items[0])


async def batch_register_function_jobs(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: ProductName,
    function_jobs: FunctionJobList,
) -> BatchCreateRegisteredFunctionJobs:
    TypeAdapter(FunctionJobList).validate_python(function_jobs)
    encoded_function_jobs = [_encode_functionjob(job) for job in function_jobs]
    created_function_jobs_db = await _function_jobs_repository.create_function_jobs(
        app=app,
        user_id=user_id,
        product_name=product_name,
        function_jobs=encoded_function_jobs,
    )
    return BatchCreateRegisteredFunctionJobs(
        created_items=[
            _decode_functionjob(job) for job in created_function_jobs_db.created_items
        ]
    )


async def patch_registered_function_job(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: ProductName,
    function_job_patch_request: FunctionJobPatchRequest,
) -> RegisteredFunctionJob:

    result = await _function_jobs_repository.patch_function_jobs(
        app=app,
        user_id=user_id,
        product_name=product_name,
        function_job_patch_requests=[function_job_patch_request],
    )
    assert len(result.updated_items) == 1  # nosec
    return _decode_functionjob(result.updated_items[0])


async def batch_patch_registered_function_jobs(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: ProductName,
    function_job_patch_requests: FunctionJobPatchRequestList,
) -> BatchUpdateRegisteredFunctionJobs:
    TypeAdapter(FunctionJobPatchRequestList).validate_python(
        function_job_patch_requests
    )

    result = await _function_jobs_repository.patch_function_jobs(
        app=app,
        user_id=user_id,
        product_name=product_name,
        function_job_patch_requests=function_job_patch_requests,
    )
    return BatchUpdateRegisteredFunctionJobs(
        updated_items=[_decode_functionjob(job) for job in result.updated_items]
    )


async def register_function_job_collection(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: ProductName,
    function_job_collection: FunctionJobCollection,
) -> RegisteredFunctionJobCollection:
    registered_function_job_collection, registered_job_ids = (
        await _function_job_collections_repository.create_function_job_collection(
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
    returned_function_job = await _function_jobs_repository.get_function_job(
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
        await _function_job_collections_repository.get_function_job_collection(
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
    order_by: OrderBy | None = None,
    filter_by_function_class: FunctionClass | None = None,
    search_by_function_title: str | None = None,
    search_by_multi_columns: str | None = None,
) -> tuple[list[RegisteredFunction], PageMetaInfoLimitOffset]:
    returned_functions, page = await _functions_repository.list_functions(
        app=app,
        user_id=user_id,
        product_name=product_name,
        pagination_limit=pagination_limit,
        pagination_offset=pagination_offset,
        order_by=(
            OrderBy(
                field=IDStr("uuid") if order_by.field == "uid" else order_by.field,
                direction=order_by.direction,
            )
            if order_by
            else None
        ),
        filter_by_function_class=filter_by_function_class,
        search_by_function_title=search_by_function_title,
        search_by_multi_columns=search_by_multi_columns,
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
    filter_by_function_job_ids: list[FunctionJobID] | None = None,
    filter_by_function_job_collection_id: FunctionJobCollectionID | None = None,
) -> tuple[list[RegisteredFunctionJob], PageMetaInfoLimitOffset]:
    returned_function_jobs, page = (
        await _function_jobs_repository.list_function_jobs_with_status(
            app=app,
            user_id=user_id,
            product_name=product_name,
            pagination_limit=pagination_limit,
            pagination_offset=pagination_offset,
            filter_by_function_id=filter_by_function_id,
            filter_by_function_job_ids=filter_by_function_job_ids,
            filter_by_function_job_collection_id=filter_by_function_job_collection_id,
        )
    )
    return [
        _decode_functionjob(returned_function_job)
        for returned_function_job in returned_function_jobs
    ], page


async def list_function_jobs_with_status(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: ProductName,
    pagination_limit: int,
    pagination_offset: int,
    filter_by_function_id: FunctionID | None = None,
    filter_by_function_job_ids: list[FunctionJobID] | None = None,
    filter_by_function_job_collection_id: FunctionJobCollectionID | None = None,
) -> tuple[
    list[RegisteredFunctionJobWithStatus],
    PageMetaInfoLimitOffset,
]:
    returned_function_jobs_wso, page = (
        await _function_jobs_repository.list_function_jobs_with_status(
            app=app,
            user_id=user_id,
            product_name=product_name,
            pagination_limit=pagination_limit,
            pagination_offset=pagination_offset,
            filter_by_function_id=filter_by_function_id,
            filter_by_function_job_ids=filter_by_function_job_ids,
            filter_by_function_job_collection_id=filter_by_function_job_collection_id,
        )
    )
    return [
        _decode_functionjob_wso(returned_function_job_wso)
        for returned_function_job_wso in returned_function_jobs_wso
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
        await _function_job_collections_repository.list_function_job_collections(
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
    force: bool = False,
) -> None:
    await _functions_repository.delete_function(
        app=app,
        user_id=user_id,
        product_name=product_name,
        function_id=function_id,
        force=force,
    )


async def delete_function_job(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: ProductName,
    function_job_id: FunctionJobID,
) -> None:
    await _function_jobs_repository.delete_function_job(
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
    await _function_job_collections_repository.delete_function_job_collection(
        app=app,
        user_id=user_id,
        product_name=product_name,
        function_job_collection_id=function_job_collection_id,
    )


async def update_function(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: ProductName,
    function_id: FunctionID,
    function: FunctionUpdate,
) -> RegisteredFunction:
    updated_function = await _functions_repository.update_function(
        app=app,
        user_id=user_id,
        product_name=product_name,
        function_id=function_id,
        function=function,
    )
    return _decode_function(updated_function)


async def find_cached_function_jobs(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: ProductName,
    function_id: FunctionID,
    inputs: FunctionInputsList,
    cached_job_statuses: list[FunctionJobStatus] | None = None,
) -> list[RegisteredFunctionJob | None]:
    returned_function_jobs = await _function_jobs_repository.find_cached_function_jobs(
        app=app,
        user_id=user_id,
        product_name=product_name,
        function_id=function_id,
        inputs=inputs,
        cached_job_statuses=cached_job_statuses,
    )
    assert len(returned_function_jobs) == len(inputs)  # nosec

    def _map_db_model_to_domain_model(
        job: RegisteredFunctionJobDB | None,
    ) -> RegisteredFunctionJob | None:
        if job is None:
            return None
        if job.function_class == FunctionClass.PROJECT:
            return RegisteredProjectFunctionJob(
                uid=job.uuid,
                title=job.title,
                description=job.description,
                function_uid=job.function_uuid,
                inputs=job.inputs,
                outputs=None,
                project_job_id=job.class_specific_data["project_job_id"],
                job_creation_task_id=job.class_specific_data.get(
                    "job_creation_task_id"
                ),
                created_at=job.created,
            )
        if job.function_class == FunctionClass.SOLVER:
            return RegisteredSolverFunctionJob(
                uid=job.uuid,
                title=job.title,
                description=job.description,
                function_uid=job.function_uuid,
                inputs=job.inputs,
                outputs=None,
                solver_job_id=job.class_specific_data.get("solver_job_id"),
                job_creation_task_id=job.class_specific_data.get(
                    "job_creation_task_id"
                ),
                created_at=job.created,
            )
        raise UnsupportedFunctionJobClassError(function_job_class=job.function_class)

    return [_map_db_model_to_domain_model(job) for job in returned_function_jobs]


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
    user_permissions = await _functions_permissions_repository.get_user_permissions(
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


async def list_function_group_permissions(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: ProductName,
    function_id: FunctionID,
) -> list[FunctionGroupAccessRights]:
    access_rights_list = await _functions_permissions_repository.get_group_permissions(
        app=app,
        user_id=user_id,
        product_name=product_name,
        object_ids=[function_id],
        object_type="function",
    )

    for object_id, access_rights in access_rights_list:
        if object_id == function_id:
            return access_rights

    raise FunctionGroupAccessRightsNotFoundError(
        function_id=function_id,
        product_name=product_name,
    )


async def set_function_group_permissions(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: ProductName,
    function_id: FunctionID,
    permissions: FunctionGroupAccessRights,
) -> FunctionGroupAccessRights:
    access_rights_list = await _functions_permissions_repository.set_group_permissions(
        app=app,
        user_id=user_id,
        product_name=product_name,
        object_ids=[function_id],
        object_type="function",
        permission_group_id=permissions.group_id,
        read=permissions.read,
        write=permissions.write,
        execute=permissions.execute,
    )
    for object_id, access_rights in access_rights_list:
        if object_id == function_id:
            return access_rights

    raise FunctionGroupAccessRightsNotFoundError(
        product_name=product_name,
        function_id=function_id,
    )


async def remove_function_group_permissions(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: ProductName,
    function_id: FunctionID,
    permission_group_id: GroupID,
) -> None:
    await _functions_permissions_repository.remove_group_permissions(
        app=app,
        user_id=user_id,
        product_name=product_name,
        object_ids=[function_id],
        object_type="function",
        permission_group_id=permission_group_id,
    )


async def set_group_permissions(
    app: web.Application,
    *,
    user_id: UserID,
    permission_group_id: GroupID,
    product_name: ProductName,
    object_type: Literal["function", "function_job", "function_job_collection"],
    object_ids: list[FunctionID | FunctionJobID | FunctionJobCollectionID],
    read: bool | None = None,
    write: bool | None = None,
    execute: bool | None = None,
) -> list[
    tuple[
        FunctionID | FunctionJobID | FunctionJobCollectionID, FunctionGroupAccessRights
    ]
]:
    return await _functions_permissions_repository.set_group_permissions(
        app=app,
        user_id=user_id,
        product_name=product_name,
        object_type=object_type,
        object_ids=object_ids,
        permission_group_id=permission_group_id,
        read=read,
        write=write,
        execute=execute,
    )


async def get_function_job_status(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: ProductName,
    function_job_id: FunctionJobID,
) -> FunctionJobStatus:
    return await _function_jobs_repository.get_function_job_status(
        app=app,
        user_id=user_id,
        product_name=product_name,
        function_job_id=function_job_id,
    )


async def get_function_job_outputs(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: ProductName,
    function_job_id: FunctionJobID,
) -> FunctionOutputs:
    return await _function_jobs_repository.get_function_job_outputs(
        app=app,
        user_id=user_id,
        product_name=product_name,
        function_job_id=function_job_id,
    )


async def update_function_job_outputs(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: ProductName,
    function_job_id: FunctionJobID,
    outputs: FunctionOutputs,
    check_write_permissions: bool = True,
) -> FunctionOutputs:
    checked_permissions: list[Literal["read", "write", "execute"]] = ["read"]
    if check_write_permissions:
        checked_permissions.append("write")
    await _functions_permissions_repository.check_user_permissions(
        app,
        user_id=user_id,
        product_name=product_name,
        object_type="function_job",
        object_id=function_job_id,
        permissions=checked_permissions,
    )

    return await _function_jobs_repository.update_function_job_outputs(
        app=app,
        function_job_id=function_job_id,
        outputs=outputs,
    )


async def update_function_job_status(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: ProductName,
    function_job_id: FunctionJobID,
    job_status: FunctionJobStatus,
    check_write_permissions: bool = True,
) -> FunctionJobStatus:
    checked_permissions: list[Literal["read", "write", "execute"]] = ["read"]

    if check_write_permissions:
        checked_permissions.append("write")
    await _functions_permissions_repository.check_user_permissions(
        app,
        user_id=user_id,
        product_name=product_name,
        object_type="function_job",
        object_id=function_job_id,
        permissions=checked_permissions,
    )
    return await _function_jobs_repository.update_function_job_status(
        app=app,
        function_job_id=function_job_id,
        job_status=job_status,
    )


async def get_functions_user_api_access_rights(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: ProductName,
) -> FunctionUserApiAccessRights:
    return await _functions_permissions_repository.get_user_api_access_rights(
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
            modified_at=function.modified,
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
            modified_at=function.modified,
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
                "project_job_id": (
                    str(functionjob.project_job_id)
                    if functionjob.project_job_id
                    else None
                ),
                "job_creation_task_id": (
                    str(functionjob.job_creation_task_id)
                    if functionjob.job_creation_task_id
                    else None
                ),
            }
        )
    elif functionjob.function_class == FunctionClass.SOLVER:
        class_specific_data = FunctionJobClassSpecificData(
            {
                "solver_job_id": (
                    str(functionjob.solver_job_id)
                    if functionjob.solver_job_id
                    else None
                ),
                "job_creation_task_id": (
                    str(functionjob.job_creation_task_id)
                    if functionjob.job_creation_task_id
                    else None
                ),
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
    functionjob_db: RegisteredFunctionJobWithStatusDB | RegisteredFunctionJobDB,
) -> RegisteredFunctionJob:
    if functionjob_db.function_class == FunctionClass.PROJECT:
        return RegisteredProjectFunctionJob(
            uid=functionjob_db.uuid,
            title=functionjob_db.title,
            description=functionjob_db.description,
            function_uid=functionjob_db.function_uuid,
            inputs=functionjob_db.inputs,
            outputs=functionjob_db.outputs,
            project_job_id=functionjob_db.class_specific_data["project_job_id"],
            job_creation_task_id=functionjob_db.class_specific_data.get(
                "job_creation_task_id"
            ),
            created_at=functionjob_db.created,
        )

    if functionjob_db.function_class == FunctionClass.SOLVER:
        return RegisteredSolverFunctionJob(
            uid=functionjob_db.uuid,
            title=functionjob_db.title,
            description=functionjob_db.description,
            function_uid=functionjob_db.function_uuid,
            inputs=functionjob_db.inputs,
            outputs=functionjob_db.outputs,
            solver_job_id=functionjob_db.class_specific_data["solver_job_id"],
            job_creation_task_id=functionjob_db.class_specific_data.get(
                "job_creation_task_id"
            ),
            created_at=functionjob_db.created,
        )

    raise UnsupportedFunctionJobClassError(
        function_job_class=functionjob_db.function_class
    )


def _decode_functionjob_wso(
    functionjob_db: RegisteredFunctionJobWithStatusDB,
) -> RegisteredFunctionJobWithStatus:
    if functionjob_db.function_class == FunctionClass.PROJECT:
        return RegisteredProjectFunctionJobWithStatus(
            uid=functionjob_db.uuid,
            title=functionjob_db.title,
            description="",
            function_uid=functionjob_db.function_uuid,
            inputs=functionjob_db.inputs,
            outputs=functionjob_db.outputs,
            project_job_id=functionjob_db.class_specific_data["project_job_id"],
            created_at=functionjob_db.created,
            status=FunctionJobStatus(status=functionjob_db.status),
            job_creation_task_id=functionjob_db.class_specific_data.get(
                "job_creation_task_id"
            ),
        )

    if functionjob_db.function_class == FunctionClass.SOLVER:
        return RegisteredSolverFunctionJobWithStatus(
            uid=functionjob_db.uuid,
            title=functionjob_db.title,
            description="",
            function_uid=functionjob_db.function_uuid,
            inputs=functionjob_db.inputs,
            outputs=functionjob_db.outputs,
            solver_job_id=functionjob_db.class_specific_data["solver_job_id"],
            created_at=functionjob_db.created,
            status=FunctionJobStatus(status=functionjob_db.status),
            job_creation_task_id=functionjob_db.class_specific_data.get(
                "job_creation_task_id"
            ),
        )

    raise UnsupportedFunctionJobClassError(
        function_job_class=functionjob_db.function_class
    )

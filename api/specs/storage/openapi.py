# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from enum import Enum
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Query, status
from models_library.api_schemas_storage import (
    FileMetaDataGet,
    FileUploadCompleteFutureResponse,
    FileUploadCompleteResponse,
    FileUploadCompletionBody,
    FileUploadSchema,
    FoldersBody,
    HealthCheck,
    LinkType,
    PresignedLink,
    SoftCopyBody,
    TableSynchronisation,
)
from models_library.app_diagnostics import AppStatusCheck
from models_library.generics import Envelope
from models_library.projects_nodes import NodeID
from models_library.projects_nodes_io import LocationID, StorageFileID
from models_library.users import UserID
from pydantic import AnyUrl, ByteSize
from servicelib.fastapi.openapi import create_openapi_specs
from servicelib.long_running_tasks._models import TaskGet, TaskId, TaskStatus
from settings_library.s3 import S3Settings
from simcore_service_storage._meta import API_VTAG
from simcore_service_storage.models import (
    DatasetMetaData,
    FileMetaData,
    SearchFilesQueryParams,
)
from simcore_service_storage.resources import storage_resources

TAGS_DATASETS: list[str | Enum] = ["datasets"]
TAGS_FILES: list[str | Enum] = ["files"]
TAGS_HEALTH: list[str | Enum] = ["health"]
TAGS_LOCATIONS: list[str | Enum] = ["locations"]
TAGS_TASKS: list[str | Enum] = ["tasks"]
TAGS_SIMCORE_S3: list[str | Enum] = ["simcore-s3"]


app = FastAPI(
    redoc_url=None,
    description="API definition for simcore-service-storage service",
    version="0.3.0",
    title="simcore-service-storage API",
    contact={"name": "IT'IS Foundation", "email": "support@simcore.io"},
    license_info={
        "name": "MIT",
        "__PLACEHOLDER___KEY_url": "https://github.com/ITISFoundation/osparc-simcore/blob/master/LICENSE",
    },
    servers=[
        {
            "url": "/",
            "description": "Default server: requests directed to serving url",
        },
        {
            "url": "http://{host}:{port}/",
            "description": "Development server: can configure any base url",
            "variables": {
                "host": {"default": "127.0.0.1"},
                "port": {"default": "8000"},
            },
        },
    ],
    openapi_tags=[
        {"name": x}
        for x in (
            TAGS_DATASETS
            + TAGS_FILES
            + TAGS_HEALTH
            + TAGS_LOCATIONS
            + TAGS_TASKS
            + TAGS_SIMCORE_S3
        )
    ],
)


# handlers_datasets.py


@app.get(
    f"/{API_VTAG}/locations/{{location_id}}/datasets",
    response_model=Envelope[list[DatasetMetaData]],
    tags=TAGS_DATASETS,
    operation_id="get_datasets_metadata",
    summary="Get datasets metadata",
)
async def get_datasets_metadata(location_id: LocationID, user_id: UserID):
    """returns all the top level datasets a user has access to"""


# handlers_files.py


@app.get(
    f"/{API_VTAG}/locations/{{location_id}}/datasets/{{dataset_id}}/metadata",
    response_model=Envelope[list[FileMetaDataGet]],
    tags=TAGS_DATASETS,
    operation_id="get_files_metadata_dataset",
    summary="Get Files Metadata",
)
async def get_files_metadata_dataset(
    location_id: LocationID,
    dataset_id: str,
    user_id: UserID,
    expand_dirs: bool = Query(
        True,
        description=(
            "Automatic directory expansion. This will be replaced by pagination the future"
        ),
    ),
):
    """returns all the file meta data inside dataset with dataset_id"""


@app.get(
    f"/{API_VTAG}/locations",
    response_model=list[DatasetMetaData],
    tags=TAGS_LOCATIONS,
    operation_id="get_storage_locations",
    summary="Get available storage locations",
)
async def get_storage_locations(user_id: UserID):
    """Returns the list of available storage locations"""


@app.post(
    f"/{API_VTAG}/locations/{{location_id}}:sync",
    response_model=Envelope[TableSynchronisation],
    tags=TAGS_LOCATIONS,
    operation_id="synchronise_meta_data_table",
    summary="Manually triggers the synchronisation of the file meta data table in the database",
)
async def synchronise_meta_data_table(
    location_id: LocationID, dry_run: bool = False, fire_and_forget: bool = False
):
    """Returns an object containing added, changed and removed paths"""


@app.get(
    f"/{API_VTAG}/locations/{{location_id}}/files/metadata",
    response_model=Envelope[list[DatasetMetaData]],
    tags=TAGS_FILES,
    operation_id="get_files_metadata",
    summary="Get datasets metadata",
)
async def get_files_metadata(
    location_id: LocationID,
    uuid_filter: str = "",
    expand_dirs: bool = Query(
        True,
        description=(
            "Automatic directory expansion. This will be replaced by pagination the future"
        ),
    ),
):
    """returns all the file meta data a user has access to (uuid_filter may be used)"""


@app.get(
    f"/{API_VTAG}/locations/{{location_id}}/files/{{file_id}}/metadata",
    response_model=FileMetaData | Envelope[FileMetaDataGet],
    tags=TAGS_FILES,
    summary="Get File Metadata",
    operation_id="get_file_metadata",
)
async def get_file_metadata(
    location_id: LocationID, file_id: StorageFileID, user_id: UserID
):
    """returns the file meta data of file_id if user_id has the rights to"""


@app.get(
    f"/{API_VTAG}/locations/{{location_id}}/files/{{file_id}}",
    response_model=Envelope[PresignedLink],
    tags=TAGS_FILES,
    operation_id="download_file",
    summary="Returns download link for requested file",
)
async def download_file(
    location_id: LocationID,
    file_id: StorageFileID,
    user_id: UserID,
    link_type: LinkType = LinkType.PRESIGNED,
):
    """creates a download file link if user has the rights to"""


@app.put(
    f"/{API_VTAG}/locations/{{location_id}}/files/{{file_id}}",
    response_model=Envelope[FileUploadSchema] | Envelope[AnyUrl],
    tags=TAGS_FILES,
    operation_id="upload_file",
    summary="Returns upload link",
)
async def upload_file(
    location_id: LocationID,
    file_id: StorageFileID,
    file_size: ByteSize | None,
    link_type: LinkType = LinkType.PRESIGNED,
    is_directory: bool = False,
):
    """creates one or more upload file links if user has the rights to, expects the client to complete/abort upload"""


@app.post(
    f"/{API_VTAG}/locations/{{location_id}}/files/{{file_id}}:abort",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=TAGS_FILES,
    operation_id="abort_upload_file",
)
async def abort_upload_file(
    location_id: LocationID, file_id: StorageFileID, user_id: UserID
):
    """aborts an upload if user has the rights to, and reverts
    to the latest version if available, else will delete the file"""


@app.post(
    f"/{API_VTAG}/locations/{{location_id}}/files/{{file_id}}:complete",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=Envelope[FileUploadCompleteResponse],
    tags=TAGS_FILES,
    operation_id="complete_upload_file",
)
async def complete_upload_file(
    body_item: Envelope[FileUploadCompletionBody],
    location_id: LocationID,
    file_id: StorageFileID,
    user_id: UserID,
):
    """completes an upload if the user has the rights to"""


@app.post(
    f"/{API_VTAG}/locations/{{location_id}}/files/{{file_id}}:complete/futures/{{future_id}}",
    response_model=Envelope[FileUploadCompleteFutureResponse],
    tags=TAGS_FILES,
    summary="Check for upload completion",
    operation_id="is_completed_upload_file",
)
async def is_completed_upload_file(
    location_id: LocationID, file_id: StorageFileID, future_id: str, user_id: UserID
):
    """Returns state of upload completion"""


# handlers_health.py


@app.get(
    f"/{API_VTAG}/",
    response_model=Envelope[HealthCheck],
    tags=TAGS_HEALTH,
    summary="health check endpoint",
    operation_id="health_check",
)
async def get_health():
    """Current service health"""


@app.get(
    f"/{API_VTAG}/status",
    response_model=Envelope[AppStatusCheck],
    tags=TAGS_HEALTH,
    summary="returns the status of the services inside",
    operation_id="get_status",
)
async def get_status():
    """returns the status of all the external dependencies"""


# handlers_locations.py


@app.delete(
    f"/{API_VTAG}/locations/{{location_id}}/files/{{file_id}}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=TAGS_FILES,
    operation_id="delete_file",
    summary="Deletes File",
)
async def delete_file(location_id: LocationID, file_id: StorageFileID, user_id: UserID):
    """deletes file if user has the rights to"""


@app.post(
    f"/{API_VTAG}/files/{{file_id}}:soft-copy",
    response_model=FileMetaDataGet,
    tags=TAGS_FILES,
    summary="copy file as soft link",
    operation_id="copy_as_soft_link",
)
async def copy_as_soft_link(
    body_item: SoftCopyBody, file_id: StorageFileID, user_id: UserID
):
    """creates and returns a soft link"""


# handlers_simcore_s3.py


@app.post(
    f"/{API_VTAG}/simcore-s3:access",
    response_model=Envelope[S3Settings],
    tags=TAGS_SIMCORE_S3,
    summary="gets or creates the a temporary access",
    operation_id="get_or_create_temporary_s3_access",
)
async def get_or_create_temporary_s3_access(user_id: UserID):
    """returns a set of S3 credentials"""


@app.post(
    f"/{API_VTAG}/simcore-s3/folders",
    response_model=Envelope[TaskGet],
    tags=TAGS_SIMCORE_S3,
    summary="copies folders from project",
    operation_id="copy_folders_from_project",
)
async def copy_folders_from_project(body_item: FoldersBody, user_id: UserID):
    """copies folders from project"""


@app.delete(
    f"/{API_VTAG}/simcore-s3/folders/{{folder_id}}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=TAGS_SIMCORE_S3,
    summary="delete folders from project",
    operation_id="delete_folders_of_project",
)
async def delete_folders_of_project(
    folder_id: str, user_id: UserID, node_id: NodeID | None = None
):
    """removes folders from a project"""


@app.post(
    f"/{API_VTAG}/simcore-s3/files/metadata:search",
    response_model=Envelope[FileMetaDataGet],
    tags=TAGS_SIMCORE_S3,
    summary="search for owned files",
    operation_id="search_files",
)
async def search_files(_query_params: Annotated[SearchFilesQueryParams, Depends()]):
    """search for files starting with `startswith` and/or matching a sha256_checksum in the file_meta_data table"""


# long_running_tasks.py


@app.get(
    f"/{API_VTAG}/futures",
    response_model=Envelope[TaskGet],
    tags=TAGS_TASKS,
    summary="list current long running tasks",
    operation_id="list_tasks",
)
async def list_tasks():
    """list current long running tasks"""


@app.get(
    f"/{API_VTAG}/futures/{{task_id}}",
    response_model=Envelope[TaskStatus],
    tags=TAGS_TASKS,
    summary="gets the status of the task",
    operation_id="get_task_status",
)
async def get_task_status(task_id: TaskId):
    """gets the status of the task"""


@app.get(
    f"/{API_VTAG}/futures/{{task_id}}/result",
    response_model=Any,
    tags=TAGS_TASKS,
    summary="get result of the task",
    operation_id="get_task_result",
)
async def get_task_result(task_id: TaskId):
    """get result of the task"""


@app.delete(
    f"/{API_VTAG}/futures/{{task_id}}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=TAGS_TASKS,
    summary="cancels and removes the task",
    operation_id="cancel_and_delete_task",
)
async def cancel_and_delete_task(task_id: TaskId):
    """cancels and removes the task"""


if __name__ == "__main__":
    openapi = create_openapi_specs(app, drop_fastapi_default_422=True)

    oas_path = storage_resources.get_path("api/v0/openapi.yaml").resolve()
    print(f"Writing {oas_path}...", end=None)

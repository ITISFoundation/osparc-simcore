import json
from pathlib import Path
from typing import List, Optional

from attr import __description__
from fastapi import APIRouter, FastAPI
from models_library.api_schemas_storage import HealthCheckEnveloped
from models_library.app_diagnostics import AppStatusCheck
from pydantic import BaseModel, HttpUrl
from simcore_service_storage.meta import api_version_prefix

router = APIRouter()


@router.get("/", response_model=HealthCheckEnveloped, operation_id="get_health")
def get_app_health():
    pass


@router.get("/status", response_model=AppStatusCheck)
def get_app_status():
    pass


files_router = APIRouter()


class ApiResource(BaseModel):
    id: str

    # self url
    url: HttpUrl


class File(ApiResource):
    storage_source: str  # simcore/datcore/google drive etc
    title: Optional[str]


class FileEdit(File):
    # nothing is required
    pass


class FileList(BaseModel):
    items: List[File]
    # tokens ...


@files_router.get("", response_model=FileList)
def list_files():
    """ Lists the user's files """


@files_router.post("/{file_id}", response_model=File)
def get_file():
    """ Gets a file's metadata or content by id"""


@files_router.post("/{file_id:path}:copy", response_model=File)
def copy_file(
    file_id: str,
    as_soft_link: bool = False,
    new_file: Optional[FileEdit] = None,
):
    """ Creates a copy of a specified file """
    print(file_id, as_soft_link, new_file)


app = FastAPI()
app.include_router(router, prefix="/v1")
app.include_router(files_router, prefix="/v1/files", tags=["files"])


def main():
    # uvicorn openapi_generator:app --reload --host 0.0.0.0
    print(json.dumps(app.openapi(), indent=2))


if __name__ == "__main__":
    main()

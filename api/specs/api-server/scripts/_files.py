from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, status
from pydantic import BaseModel
from pydantic.fields import Field
from starlette.responses import RedirectResponse

# MODELS -----------------------------------------------------------------------------------------


class File(BaseModel):
    id: UUID = Field(..., description="Resource identifier")

    filename: str = Field(..., description="Name of the file with extension")
    content_type: Optional[str] = Field(
        None, description="Guess of type content [EXPERIMENTAL]"
    )
    checksum: Optional[str] = Field(
        None, description="MD5 hash of the file's content [EXPERIMENTAL]"
    )


# ROUTES -----------------------------------------------------------------------------------------

router = APIRouter()


@router.get("/files", response_model=List[File])
def list_files():
    ...


@router.put("/content", response_model=File)
def upload_file():
    ...


@router.get(
    "/{file_id}",
    response_model=File,
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "File not found"},
    },
)
def get_file(
    file_id: UUID,
):
    ...


@router.get(
    "/{file_id}/content",
    response_class=RedirectResponse,
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "File not found"},
        status.HTTP_200_OK: {
            "content": {
                "application/octet-stream": {
                    "schema": {"type": "string", "format": "binary"}
                },
                "text/plain": {"schema": {"type": "string"}},
            },
            "description": "Returns a arbitrary binary data",
        },
    },
)
def download_file(file_id: UUID):
    ...

from typing import Annotated
from uuid import UUID

from models_library.api_schemas_storage.storage_schemas import ETag
from models_library.basic_types import SHA256Str
from pydantic import (
    AnyHttpUrl,
    BaseModel,
    ConfigDict,
    Field,
    NonNegativeInt,
    StringConstraints,
)
from simcore_service_api_server.models.schemas.programs import ProgramJobFilePath

from .._utils_pydantic import UriSchema
from ..domain.files import File as _File
from ._utils import ApiServerInputSchema, ApiServerOutputSchema

NAMESPACE_FILEID_KEY = UUID("aa154444-d22d-4290-bb15-df37dba87865")


FileName = Annotated[str, StringConstraints(strip_whitespace=True)]


class ClientFile(ApiServerInputSchema):
    """Represents a file stored on the client side"""

    filename: FileName = Field(..., description="File name")
    filesize: NonNegativeInt = Field(..., description="File size in bytes")
    sha256_checksum: SHA256Str = Field(..., description="SHA256 checksum")
    destination: Annotated[
        ProgramJobFilePath | None,
        Field(..., description="Destination within a program job"),
    ]


class File(ApiServerOutputSchema):
    """Represents a file stored on the server side i.e. a unique reference to a file in the cloud."""

    # WARNING: from pydantic import File as FileParam
    # NOTE: see https://ant.apache.org/manual/Tasks/checksum.html

    id: UUID = Field(..., description="Resource identifier")

    filename: str = Field(..., description="Name of the file with extension")
    content_type: str | None = Field(
        default=None,
        description="Guess of type content [EXPERIMENTAL]",
        validate_default=True,
    )
    sha256_checksum: SHA256Str | None = Field(
        default=None,
        description="SHA256 hash of the file's content",
        alias="checksum",  # alias for backwards compatibility
    )
    e_tag: ETag | None = Field(default=None, description="S3 entity tag")

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "examples": [
                # complete
                {
                    "id": "f0e1fb11-208d-3ed2-b5ef-cab7a7398f78",
                    "filename": "Architecture-of-Scalable-Distributed-ETL-System-whitepaper.pdf",
                    "content_type": "application/pdf",
                    "checksum": "1a512547e3ce3427482da14e8c914ecf61da76ad5f749ff532efe906e6bba128",
                },
                # minimum
                {
                    "id": "f0e1fb11-208d-3ed2-b5ef-cab7a7398f78",
                    "filename": "whitepaper.pdf",
                },
            ]
        },
    )

    @classmethod
    def from_domain_model(cls, file: _File) -> "File":
        return cls(
            id=file.id,
            filename=file.filename,
            content_type=file.content_type,
            checksum=file.sha256_checksum,
            e_tag=file.e_tag,
        )


class UploadLinks(BaseModel):
    abort_upload: str
    complete_upload: str


class FileUploadData(BaseModel):
    chunk_size: NonNegativeInt
    urls: list[Annotated[AnyHttpUrl, UriSchema()]]
    links: UploadLinks


class ClientFileUploadData(BaseModel):
    file_id: UUID = Field(..., description="The file resource id")
    upload_schema: FileUploadData = Field(..., description="Schema for uploading file")

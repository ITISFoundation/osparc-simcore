import datetime
from mimetypes import guess_type
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
    ValidationInfo,
    field_validator,
)

from .._utils_pydantic import UriSchema
from ..domain.files import File as DomainFile
from ..domain.files import FileName
from .base import ApiServerInputSchema, ApiServerOutputSchema


class UserFile(ApiServerInputSchema):
    """Represents a file stored on the client side"""

    filename: Annotated[FileName, Field(..., description="File name")]
    filesize: Annotated[NonNegativeInt, Field(..., description="File size in bytes")]
    sha256_checksum: Annotated[SHA256Str, Field(..., description="SHA256 checksum")]

    def to_domain_model(
        self,
        file_id: UUID | None = None,
    ) -> DomainFile:
        return DomainFile(
            id=(
                file_id
                if file_id
                else DomainFile.create_id(
                    self.filesize,
                    self.filename,
                    datetime.datetime.now(datetime.UTC).isoformat(),
                )
            ),
            filename=self.filename,
            checksum=self.sha256_checksum,
            program_job_file_path=None,
        )


class File(ApiServerOutputSchema):
    """Represents a file stored on the server side i.e. a unique reference to a file in the cloud."""

    id: Annotated[UUID, Field(..., description="Resource identifier")]
    filename: Annotated[str, Field(..., description="Name of the file with extension")]
    content_type: Annotated[
        str | None,
        Field(
            default=None,
            description="Guess of type content [EXPERIMENTAL]",
            validate_default=True,
        ),
    ] = None
    sha256_checksum: Annotated[
        SHA256Str | None,
        Field(
            default=None,
            description="SHA256 hash of the file's content",
            alias="checksum",  # alias for backwards compatibility
        ),
    ] = None
    e_tag: Annotated[ETag | None, Field(default=None, description="S3 entity tag")] = (
        None
    )

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

    @field_validator("content_type", mode="before")
    @classmethod
    def guess_content_type(cls, v, info: ValidationInfo):
        if v is None:
            filename = info.data.get("filename")
            if filename:
                mime_content_type, _ = guess_type(filename, strict=False)
                return mime_content_type
        return v

    @classmethod
    def from_domain_model(cls, file: DomainFile) -> "File":
        return cls(
            id=file.id,
            filename=file.filename,
            content_type=file.content_type,
            sha256_checksum=file.sha256_checksum,
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

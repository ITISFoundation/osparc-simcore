import datetime
from pathlib import Path
from typing import Annotated

from models_library.api_schemas_datcore_adapter.datasets import PackageMetaData
from pydantic import AnyUrl, BaseModel, ByteSize, Field


class FileDownloadOut(BaseModel):
    link: AnyUrl


class DatCorePackageMetaData(BaseModel):
    id: int
    path: Path
    display_path: Path
    package_id: Annotated[str, Field(alias="packageId")]
    name: str
    filename: str
    s3_bucket: Annotated[str, Field(alias="s3bucket")]
    size: ByteSize
    created_at: Annotated[datetime.datetime, Field(alias="createdAt")]
    updated_at: Annotated[datetime.datetime, Field(alias="updatedAt")]

    def to_api_model(self) -> PackageMetaData:
        return PackageMetaData(
            path=self.path,
            display_path=self.display_path,
            package_id=self.package_id,
            name=self.name,
            filename=self.filename,
            s3_bucket=self.s3_bucket,
            size=self.size,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )

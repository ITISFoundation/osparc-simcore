from pydantic.main import BaseModel
from pydantic.networks import AnyUrl

from ..schemas.datasets import DatasetMetaData, FileMetaData


class DatasetsOut(DatasetMetaData):
    pass


class FileMetaDataOut(FileMetaData):
    pass


class FileDownloadOut(BaseModel):
    link: AnyUrl

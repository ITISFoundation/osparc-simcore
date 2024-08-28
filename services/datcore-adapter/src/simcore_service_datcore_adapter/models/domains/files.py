from pydantic.v1 import AnyUrl, BaseModel


class FileDownloadOut(BaseModel):
    link: AnyUrl

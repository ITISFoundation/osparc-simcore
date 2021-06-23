from pydantic import AnyUrl, BaseModel


class FileDownloadOut(BaseModel):
    link: AnyUrl

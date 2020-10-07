from pydantic import BaseModel, HttpUrl

from typing import Optional

class FileUploaded(BaseModel):
    """ Describes a file on the server side """
    filename: str
    content_type: str
    hash: str
    download_url: Optional[HttpUrl] = None

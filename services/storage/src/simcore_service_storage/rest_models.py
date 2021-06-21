""" RestAPI models

"""
from datetime import datetime

from pydantic import BaseModel


class FileMetaData(BaseModel):
    filename: str
    version: str
    last_accessed: datetime
    owner: str
    storage_location: str

# pylint: skip-file

from typing import List

import yaml
from fastapi import FastAPI
from pydantic import BaseModel, Field
from pydantic.networks import HttpUrl
from pydantic.types import PositiveInt
from yaml import safe_dump

app = FastAPI()


class FileType2Viewer(BaseModel):
    file_type: str
    viewer_title: str = Field(
        ..., description="Short formatted label with name and version of the viewer"
    )
    redirection_url: HttpUrl = Field(
        ...,
        description="Base url to redirect to this viewer. Needs appending file_size, [file_name] and download_link",
    )


@app.get("v0/viewers/filetypes", response_model=List[FileType2Viewer], tags=["viewer"])
def list_supported_filetypes():
    pass


@app.get("v0/viewers", response_model=FileType2Viewer, tags=["viewer"])
def get_viewer_for_file(file_name: str, file_size: PositiveInt, file_type: str):
    pass


with open("openapi-viewer.yaml", "wt") as fh:
    yaml.safe_dump(app.openapi(), fh)

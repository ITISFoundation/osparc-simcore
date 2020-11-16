# pylint: skip-file

from typing import List, Optional

import yaml
from fastapi import FastAPI
from fastapi.routing import APIRoute
from pydantic import BaseModel, Field
from pydantic.networks import HttpUrl
from pydantic.types import PositiveInt
from yaml import safe_dump

app = FastAPI()



# TODO:
#class ErrorType(BaseModel):
#    logs: List[LogMessageType] = []
#    errors: List[ErrorItemType]
#    status: int

class FileType2Viewer(BaseModel):
    file_type: str
    viewer_title: str = Field(
        ..., description="Short formatted label with name and version of the viewer"
    )
    redirection_url: HttpUrl = Field(
        ...,
        description="Base url to redirect to this viewer. Needs appending file_size, [file_name] and download_link",
    )


class FielType2ViewerEnveloped(BaseModel):
    data: FileType2Viewer
    # error: Optional[ErrorType] = None

class FieldType2ViewerListEnveloped(BaseModel):
    data: List[FileType2Viewer]


@app.get("/viewers/filetypes", response_model=FieldType2ViewerListEnveloped, tags=["viewer"])
def list_supported_filetypes():
    pass


@app.get("/viewers", response_model=FielType2ViewerEnveloped, tags=["viewer"])
def get_viewer_for_file(
    file_type: str,
    file_name: Optional[str] = None,
    file_size: Optional[PositiveInt] = None
    #Field(
    #    None, description="Expected file size in bytes"
    #),
):
    pass


# use handler names as operation_id
for route in app.routes:
    if isinstance(route, APIRoute):
        route.operation_id = route.name

# generate file
with open("openapi-viewer.ignore.yaml", "wt") as fh:
    yaml.safe_dump(app.openapi(), fh)

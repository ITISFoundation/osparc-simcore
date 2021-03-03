# pylint: skip-file

import json
from typing import List, Optional

import yaml
from fastapi import FastAPI
from pydantic import BaseModel
from simcore_service_webserver.studies_dispatcher.handlers_rest import (
    Viewer,
    list_default_viewers,
    list_viewers,
)

app = FastAPI()


# TODO:
# class ErrorType(BaseModel):
#    logs: List[LogMessageType] = []
#    errors: List[ErrorItemType]
#    status: int


class ViewerEnveloped(BaseModel):
    data: Viewer
    # error: Optional[ErrorType] = None


class ViewerListEnveloped(BaseModel):
    data: List[Viewer]


@app.get(
    "/viewers",
    response_model=ViewerListEnveloped,
    tags=["viewer"],
    description=list_viewers.__doc__,
    operation_id=list_viewers.__name__,
)
def list_viewers_handler(
    file_type: Optional[str] = None,
):
    pass


@app.get(
    "/viewers/default",
    response_model=ViewerEnveloped,
    tags=["viewer"],
    description=list_default_viewers.__doc__,
    operation_id=list_default_viewers.__name__,
)
def list_default_viewers_handler(
    file_type: Optional[str] = None,
):
    pass


print(json.dumps(app.openapi(), indent=2))
print("-" * 10)
print(yaml.safe_dump(app.openapi()))

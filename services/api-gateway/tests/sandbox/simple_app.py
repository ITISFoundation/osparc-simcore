# pylint: disable-all
# fmt: off

import json
from pathlib import Path
from typing import Dict, List, Tuple

import uvicorn
from fastapi import Depends, FastAPI
from fastapi.requests import Request
from pydantic import BaseModel

app = FastAPI(title="My app")


def _get_app(request: Request) -> FastAPI:
    return request.app


def get_my_user_id(app: FastAPI):
    return 3


class ItemFOO(BaseModel):
    name: str
    description: str = None
    price: float
    tax: float = None


@app.post("/studies")
async def get_studies(q1: int, body: List[ItemFOO]) -> ItemFOO:

    return body


def dump_oas():
    Path("openapi.json").write_text(json.dumps(app.openapi(), indent=2))


app.add_event_handler("startup", dump_oas)

if __name__ == "__main__":

    uvicorn.run("simple_app:app", reload=True, port=8002)

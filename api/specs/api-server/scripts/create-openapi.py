import sys

import _files
import _meta
import _solvers
import _users
import yaml
from fastapi import APIRouter, FastAPI

app = FastAPI(
    title="api-server",
    version="0.3.0",
    servers=[
        {
            "description": "up-devel",
            "url": "http://{host}:{port}",
            "variables": {
                "host": {"default": "127.0.0.1"},
                "port": {"default": "3006"},
            },
        },
    ],
)


router = APIRouter()
router.include_router(_meta.router, tags=["meta"], prefix="/meta")
router.include_router(_users.router, tags=["users"], prefix="/me")
router.include_router(_files.router, tags=["files"], prefix="/files")
router.include_router(_solvers.router, tags=["solvers"], prefix="/solvers")

app.include_router(router, prefix="/v0")


if __name__ == "__main__":

    yaml.safe_dump(app.openapi(), sys.stdout, indent=2, sort_keys=False)

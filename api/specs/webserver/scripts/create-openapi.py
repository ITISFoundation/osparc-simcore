import sys

import _projects
import _projects_meta
import _projects_repos
import yaml
from __common import override_fastapi_openapi_method
from fastapi import APIRouter, FastAPI
from packaging.version import Version

version = Version("1.0.0")

app = FastAPI(
    title="webserver",
    version=version.public,
    servers=[
        {
            "description": "up-devel",
            "url": "http://{host}:{port}",
            "variables": {
                "host": {"default": "127.0.0.1"},
                "port": {"default": "8080"},
            },
        },
    ],
)

router = APIRouter()
router.include_router(_projects_meta.router, tags=["meta-projects"], prefix="/projects")

if 0:
    router.include_router(_projects.router, tags=["projects"], prefix="/projects")
    router.include_router(
        _projects_repos.router, tags=["version control"], prefix="/projects"
    )

app.include_router(router, prefix=f"/v{version.major:1d}")
override_fastapi_openapi_method(app)

if __name__ == "__main__":

    yaml.safe_dump(app.openapi(), sys.stdout, indent=2, sort_keys=False)

""" Helper script to generate OAS automatically
"""

# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from fastapi import FastAPI

from . import (
    openapi_admin,
    openapi_announcements,
    openapi_auth,
    openapi_nih_sparc,
    openapi_projects_comments,
    openapi_projects_crud,
    openapi_projects_metadata,
    openapi_projects_nodes,
    openapi_projects_ports,
    openapi_resource_usage,
    openapi_storage,
    openapi_tags,
    openapi_users,
)

app = FastAPI(
    title="osparc-simcore web API",
    version="0.18.0",
    description="API designed for the front-end app",
    contact={"name": "IT'IS Foundation", "email": "support@simcore.io"},
    license={
        "name": "MIT",
        "url": "https://github.com/ITISFoundation/osparc-simcore/blob/master/LICENSE",
    },
    servers=[
        {
            "description": "Development server",
            "url": "http://{host}:{port}",
            "variables": {
                "host": {"default": "localhost"},
                "port": {"default": "8001"},
            },
        },
    ],
)
for m in (
    openapi_admin,
    openapi_announcements,
    openapi_auth,
    openapi_nih_sparc,
    openapi_projects_comments,
    openapi_projects_crud,
    openapi_projects_metadata,
    openapi_projects_nodes,
    openapi_projects_ports,
    openapi_resource_usage,
    openapi_storage,
    openapi_tags,
    openapi_users,
):
    app.include_router(m.router)

if __name__ == "__main__":
    from _common import create_and_save_openapi_specs

    create_and_save_openapi_specs(app, "openapi.yaml")

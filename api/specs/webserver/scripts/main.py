""" Helper script to generate OAS automatically
"""

# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


import openapi_admin
import openapi_announcements
import openapi_auth
import openapi_computations
import openapi_diagnostics
import openapi_groups
import openapi_nih_sparc
import openapi_projects_comments
import openapi_projects_crud
import openapi_projects_metadata
import openapi_projects_nodes
import openapi_projects_ports
import openapi_resource_usage
import openapi_storage
import openapi_tags
import openapi_users
import yaml
from fastapi import FastAPI
from simcore_service_webserver._resources import webserver_resources

app = FastAPI(
    title="osparc-simcore web API",
    version="0.25.0",
    description="API designed for the front-end app",
    contact={"name": "IT'IS Foundation", "email": "support@simcore.io"},
    license={
        "name": "MIT",
        "url": "https://github.com/ITISFoundation/osparc-simcore/blob/master/LICENSE",
    },
    servers=[
        {"description": "API web-server", "url": ""},
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
    openapi_computations,
    openapi_diagnostics,
    openapi_groups,
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
    from _common import create_openapi_specs

    openapi = create_openapi_specs(app, remove_main_sections=False)

    # .yaml
    oas_path = webserver_resources.get_path("/api/v0/openapi.yaml")
    with oas_path.open("wt") as fh:
        yaml.safe_dump(openapi, stream=fh, sort_keys=False)

    # .json
    # oas_path = oas_path.with_suffix(".json")
    # oas_path.write_text(json.dumps(openapi, indent=1, sort_keys=False))

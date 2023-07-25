""" Helper script to generate OAS automatically
"""

# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

import importlib

import yaml
from fastapi import FastAPI
from simcore_service_webserver._resources import webserver_resources

openapi_modules = [
    importlib.import_module(name)
    for name in (
        "openapi_activity",
        "openapi_admin",
        "openapi_announcements",
        "openapi_auth",
        "openapi_catalog",
        "openapi_cluster",
        "openapi_computations",
        "openapi_diagnostics",
        # "openapi_exporter",
        "openapi_groups",
        # "openapi_metamodeling",
        "openapi_nih_sparc",
        "openapi_projects_comments",
        "openapi_projects_crud",
        "openapi_projects_metadata",
        "openapi_projects_nodes",
        "openapi_projects_ports",
        "openapi_projects_tags",
        # "openapi_projects",
        "openapi_publications",
        "openapi_resource_usage",
        "openapi_storage",
        "openapi_tags",
        # "openapi_tasks",
        "openapi_users",
        # "openapi_version_control",
    )
]


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

for m in openapi_modules:
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

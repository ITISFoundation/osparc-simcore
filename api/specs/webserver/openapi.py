# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

import importlib

import yaml
from _common import create_openapi_specs
from fastapi import FastAPI
from fastapi.routing import APIRoute
from simcore_service_webserver._meta import API_VERSION, PROJECT_NAME, SUMMARY
from simcore_service_webserver._resources import webserver_resources

openapi_modules = [
    importlib.import_module(name)
    for name in (
        "_activity",
        "_admin",
        "_announcements",
        "_auth",
        "_catalog",
        "_cluster",
        "_computations",
        "_diagnostics",
        "_exporter",
        "_groups",
        "_long_running_tasks",
        "_metamodeling",
        "_nih_sparc_redirections",
        "_nih_sparc",
        "_projects_comments",
        "_projects_crud",
        "_projects_metadata",
        "_projects_nodes",
        "_projects_ports",
        "_projects_states",
        "_projects_tags",
        "_publications",
        "_resource_usage",
        "_storage",
        "_tags",
        "_users",
        "_version_control",
    )
]


def main():
    app = FastAPI(
        title=PROJECT_NAME,
        version=API_VERSION,
        description=SUMMARY,
        license={
            "name": "MIT",
            "url": "https://github.com/ITISFoundation/osparc-simcore/blob/master/LICENSE",
        },
        servers=[
            {"description": "webserver", "url": ""},
            {
                "description": "development server",
                "url": "http://{host}:{port}",
                "variables": {
                    "host": {"default": "localhost"},
                    "port": {"default": "8001"},
                },
            },
        ],
    )

    for module in openapi_modules:
        # enforces operation_id == handler function name
        for route in module.router.routes:
            if isinstance(route, APIRoute) and route.operation_id is None:
                route.operation_id = route.endpoint.__name__
        #
        app.include_router(module.router)

    openapi = create_openapi_specs(app, remove_main_sections=False)

    # .yaml
    oas_path = webserver_resources.get_path("/api/v0/openapi.yaml")
    print(f"Writing {oas_path}...", end=None)
    with oas_path.open("wt") as fh:
        yaml.safe_dump(openapi, stream=fh, sort_keys=False)
    print("done")

    # .json


if __name__ == "__main__":
    main()

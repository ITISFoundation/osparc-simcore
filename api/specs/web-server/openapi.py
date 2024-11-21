# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

import importlib

import yaml
from fastapi import FastAPI
from fastapi.routing import APIRoute
from servicelib.fastapi.openapi import create_openapi_specs
from simcore_service_webserver._meta import API_VERSION, PROJECT_NAME, SUMMARY
from simcore_service_webserver._resources import webserver_resources

openapi_modules = [
    importlib.import_module(name)
    for name in (
        # NOTE: order matters on how the paths are displayed in the OAS!
        # It does not have to be alphabetical
        #
        # core ---
        "_auth",
        "_groups",
        "_tags",
        "_tags_groups",  # after _tags
        "_products",
        "_users",
        "_wallets",
        # add-ons ---
        "_activity",
        "_announcements",
        "_catalog",
        "_catalog_tags",  # MUST BE after _catalog
        "_cluster",
        "_computations",
        "_exporter",
        "_folders",
        "_long_running_tasks",
        "_metamodeling",
        "_nih_sparc",
        "_nih_sparc_redirections",
        "_projects_crud",
        "_projects_comments",
        "_projects_folders",
        "_projects_groups",
        "_projects_metadata",
        "_projects_nodes",
        "_projects_nodes_pricing_unit",  # after _projects_nodes
        "_projects_ports",
        "_projects_states",
        "_projects_tags",
        "_projects_wallet",
        "_projects_workspaces",
        "_publications",
        "_resource_usage",
        "_statics",
        "_storage",
        "_trash",
        "_version_control",
        "_workspaces",
        # maintenance ----
        "_admin",
        "_diagnostics",
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
        app.include_router(module.router)

    openapi = create_openapi_specs(app, remove_main_sections=False)

    # .yaml
    oas_path = webserver_resources.get_path("api/v0/openapi.yaml").resolve()
    print(f"Writing {oas_path}...", end=None)
    with oas_path.open("wt") as fh:
        yaml.safe_dump(openapi, stream=fh, sort_keys=False)
    print("done")


if __name__ == "__main__":
    main()

# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

import importlib
import json

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
        "_auth_api_keys",
        "_conversations",
        "_groups",
        "_tags",
        "_tags_groups",  # after _tags
        "_products",
        "_users",
        "_users_admin",  # after _users
        "_wallets",
        # add-ons ---
        "_activity",
        "_announcements",
        "_catalog",
        "_catalog_tags",  # MUST BE after _catalog
        "_computations",
        "_exporter",
        "_folders",
        "_functions",
        "_long_running_tasks",
        "_long_running_tasks_legacy",
        "_licensed_items",
        "_licensed_items_purchases",
        "_licensed_items_checkouts",
        "_nih_sparc",
        "_nih_sparc_redirections",
        "_notifications",
        "_projects",
        "_projects_access_rights",
        "_projects_conversations",
        "_projects_folders",
        "_projects_metadata",
        "_projects_nodes",
        "_projects_nodes_pricing_unit",  # after _projects_nodes
        "_projects_ports",
        "_projects_states",
        "_projects_tags",
        "_projects_wallet",
        "_projects_workspaces",
        "_resource_usage",
        "_statics",
        "_storage",
        "_trash",
        "_workspaces",
        # maintenance ----
        "_diagnostics",
    )
]


def _enrich_order_by_params(openapi: dict) -> None:
    """Patch order_by query params with description and examples.

    FastAPI's Depends() pattern strips Query() metadata, so we post-process the spec.
    Only patches endpoints using the new comma-separated format (skips JSON-serialized).
    """
    description = (
        "Comma-separated list of field names for sorting. "
        "Prefix with '-' for descending, '+' or no prefix for ascending."
    )
    examples = ["-name,email", "email", "-status"]
    for path_item in openapi.get("paths", {}).values():
        for operation in path_item.values():
            if not isinstance(operation, dict):
                continue
            for param in operation.get("parameters", []):
                if param.get("name") == "order_by" and param.get("in") == "query":
                    # Skip endpoints still using JSON-serialized order_by
                    if param.get("schema", {}).get("contentMediaType") == "application/json":
                        continue
                    param["description"] = description
                    param["schema"]["description"] = description
                    param["schema"]["examples"] = examples


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
    _enrich_order_by_params(openapi)

    # .json
    oas_path = webserver_resources.get_path("api/v0/openapi.json").resolve()
    if not oas_path.exists():
        oas_path.parent.mkdir(parents=True)
        oas_path.write_text("")
    print(f"Writing {oas_path}...", end=None)  # noqa: T201
    with oas_path.open("wt") as fh:
        json.dump(openapi, fh, sort_keys=False, indent=2)
    print("done")  # noqa: T201


if __name__ == "__main__":
    main()

from fastapi import FastAPI
from fastapi.routing import APIRoute
from servicelib.fastapi.openapi import override_fastapi_openapi_method

override_openapi_method = override_fastapi_openapi_method


def use_route_names_as_operation_ids(app: FastAPI) -> None:
    """
    Overrides default operation_ids assigning the same name as the handler functions

    MUST be called only after all routes have been added.

    PROS: auto-generated client has one-to-one correspondence and human readable names
    CONS: highly coupled. Changes in server handler names will change client
    """
    for route in app.routes:
        if isinstance(route, APIRoute):
            route.operation_id = route.name

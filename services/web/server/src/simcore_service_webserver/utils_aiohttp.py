import io

from aiohttp.web_routedef import RouteDef, RouteTableDef


def rename_routes_as_handler_function(routes: RouteTableDef, *, prefix: str):
    route: RouteDef
    for route in routes:  # type: ignore
        route.kwargs["name"] = f"{prefix}.{route.handler.__name__}"


def view_routes(routes: RouteTableDef):
    fh = io.StringIO()
    print(routes, file=fh)
    for r in routes:
        print(" ", r, file=fh)
    return fh.getvalue()

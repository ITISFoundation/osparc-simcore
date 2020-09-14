import json
from pathlib import Path

from aiohttp import web
from aiohttp.web import middleware
from multidict import MultiDict

from simcore_service_webserver.__version__ import api_vtag



# FRONT_END ####################################
frontend_folder = Path.home() / "devp/osparc-simcore/services/web/client"

frontend_info = json.loads((frontend_folder / "compile.json").read_text())

target = next(
    t for t in frontend_info["targets"] if t["type"] == frontend_info["defaultTarget"]
)
frontend_outdir = frontend_folder / target["outputPath"]

frontend_apps = [feapp["name"] for feapp in frontend_info["applications"]]
default_frontend_app = next(
    feapp["name"] for feapp in frontend_info["applications"] if feapp["default"]
)


print("Client")
print("  - info           : ", frontend_info)
print("  - outdir         : ", frontend_outdir)
print("  - feapps         : ", frontend_apps)
print("  - default feapps : ", default_frontend_app)


# ----
PRODUCT_NAME_HEADER = "X-Simcore-Products-Name"
RQ_PRODUCT_HEADER_KEY = "Simcore-Products-Name"

routes = web.RouteTableDef()

(frontend_outdir / "resource" / "statics.json").write_text(
    json.dumps({"appName": "demo"})
)


#
# http://localhost:9081/
#
# http://localhost:9081/osparc/index.html#
# http://localhost:9081/s4l/index.html#
# http://localhost:9081/tis/index.html#

#
# http://localhost:9081/explorer/index.html#
# http://localhost:9081/apiviewer/index.html#
# http://localhost:9081/testtapper/index.html#


## MAIN ENTRYPOINT #############################
@routes.get("/")
async def serve_default_app(request):
    # TODO: check url and defined what is the default??
    print("Request from", request.headers["Host"])
    target_product = "s4l"  # default_frontend_app

    print("Serving front-end for product", target_product)
    raise web.HTTPFound(f"/{target_product}/index.html#")


@middleware
async def append_product_header_middleware(request, handler):
    # this is only for api? /v0/ like
    if request.path.startswith(f"/{api_vtag}"):
        print(request.path, "<---------------")
        # match url with products

        # import pdb; pdb.set_trace()
        # request.host
        request[RQ_PRODUCT_HEADER_KEY] = default_frontend_app

        # if successful, just
        # request.headers[PRODUCT_NAME_HEADER] = product_name

    return await handler(request)

## API ###################################
@routes.get("/v0/")
async def get_info(request):
    for key in request.headers:
        print(f"{key:5s}:", request.headers[key])

    # name = request.headers[PRODUCT_NAME_HEADER]
    # print("Product", name)

    return web.json_response(
        {k: str(v) for k, v in request.headers.items()},
        headers=MultiDict({PRODUCT_NAME_HEADER: default_frontend_app}),
    )


#####################################
app_port = 9081
base_path = f"http://localhost:{app_port}"
print(f"{base_path}/")
for name in frontend_apps:
    print(f"{base_path}/{name}/index.html#")

for name in frontend_apps + [
    "resource",
]:  # "transpiled"]:
    folder = frontend_outdir / name
    assert folder.exists()
    print("serving", folder)
    routes.static(f"/{folder.name}", folder, show_index=True, follow_symlinks=True)


app = web.Application(
    middlewares=[
        append_product_header_middleware,
    ]
)
app.add_routes(routes)

# print(routes, "-"*10)
# for resource in app.router.resources():
#    print(resource)

web.run_app(app, port=app_port)

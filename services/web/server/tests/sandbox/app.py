from aiohttp import web
import json
from pathlib import Path
from multidict import MultiDict

client_folder = Path.home() / "devp/osparc-simcore/services/web/client"

client_info = json.loads((client_folder / "compile.json").read_text())

target = next(t for t in client_info["targets"] if t["type"] == "source")
client_outdir = client_folder / target["outputPath"]

# ----

routes = web.RouteTableDef()
client_apps = [ capp["name"] for capp in client_info["applications"]]

default_app_name = next( capp["name"] for capp in client_info["applications"] if capp["default"] )

PRODUCT_NAME_HEADER = "X-Simcore-Products-Name"



#
import json
(client_outdir / "resource" / "statics.json").write_text(json.dumps({"appName": "demo"}))




#
# http://localhost:8080/
#
# http://localhost:8080/osparc/index.html#
# http://localhost:8080/s4l/index.html#
# http://localhost:8080/tis/index.html#

#
# http://localhost:8080/explorer/index.html#
# http://localhost:8080/apiviewer/index.html#
# http://localhost:8080/testtapper/index.html#


## MAIN ENTRYPOINT #############################
@routes.get("/")
async def serve_default_app(request):
    # TODO: check url and defined what is the default??
    print("Request from", request.headers['Host'])
    target_product = "s4l" # default_app_name

    raise web.HTTPFound(f"/{target_product}/index.html#")




## API ###################################
@routes.get("/v0/")
async def get_info(request):
    for key in request.headers:
        print(f"{key:5s}:", request.headers[key])

    #name = request.headers[PRODUCT_NAME_HEADER]
    #print("Product", name)

    return web.json_response( { k:str(v) for k,v in request.headers.items() }, headers=MultiDict({PRODUCT_NAME_HEADER: default_app_name}) )



#####################################

base_path = "http://localhost:8080"
print(f"{base_path}/")
for name in client_apps:
    print(f"{base_path}/{name}/index.html#")

for name in client_apps + ["resource", "transpiled"]:
    folder = client_outdir / name
    assert folder.exists()
    routes.static(f"/{folder.name}", folder, show_index=True, follow_symlinks=True)




app = web.Application()
app.add_routes(routes)

#print(routes, "-"*10)
#for resource in app.router.resources():
#    print(resource)

web.run_app(app)

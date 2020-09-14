from aiohttp import web
import json
from pathlib import Path


client_folder = Path.home() / "devp/osparc-simcore/services/web/client"

client_info = json.loads((client_folder / "compile.json").read_text())

target = next(t for t in client_info["targets"] if t["type"] == "source")
client_outdir = client_folder / target["outputPath"]

# ----

routes = web.RouteTableDef()

client_apps = [ capp["name"] for capp in client_info["applications"]]


#@routes.get("/")
async def default_app(request):
    index_path = client_outdir / client_app / "index.html"
    return web.Response(text=index_path.read_text(), content_type="text/html")


@routes.get("/v0/{name}")
async def get_info(request):
    name = request.match_info["name"]
    for a in client_info["applications"]:
        if a["name"] == name:
            return web.json_response(a)
    return web.Response(text=f"I know nothing about {name}")

for name in client_apps:
    print(f"http://localhost:8080/{name}/index.html#")

for name in client_apps + ["resource", "transpiled"]:
    folder = client_outdir / name
    assert folder.exists()
    print(folder)
    routes.static(f"/{folder.name}", folder, show_index=True, follow_symlinks=True)


# routes = [web.get('/v0/'), ]

app = web.Application()
app.add_routes(routes)

print(routes, "-"*10)
for resource in app.router.resources():
    print(resource)

web.run_app(app)

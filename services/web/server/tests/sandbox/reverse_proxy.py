""" Manual exploratory testing for reverse_proxy subsystem


Jupyter:

    $ cd services/dy-jupyter
    $ cp .env-devel .venv # set SIMCORE_NODE_BASEPATH=/x/12345
    $ make build-devel
    $ make up-devel


"""
from aiohttp import web

import simcore_service_webserver.reverse_proxy.handlers as rp_handlers
from simcore_service_webserver.reverse_proxy import APP_SOCKETS_KEY

if __name__ == "__main__":
    BASE_URL = "http://0.0.0.0:8888"
    MOUNT_POINT = "/x/12345"

    def adapter(req: web.Request):
        return rp_handlers.generic.handler(req, service_url=BASE_URL)
        # return rp_handlers.jupyter.handler(req, service_url=BASE_URL)

    app = web.Application()
    app[APP_SOCKETS_KEY] = list()
    app.router.add_route("*", MOUNT_POINT + "/{proxyPath:.*}", adapter)
    web.run_app(app, port=3984)

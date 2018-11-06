""" rest - Open API specifications


"""

from aiohttp import web

from .openapi import Spec, create_specs
from .application_keys import APP_OPENAPI_SPECS_KEY


# TODO consider the case of multiple versions of spec -> Dict[Spec] ??

def set_specs(app: web.Application, specs: Spec) -> Spec:
    app[APP_OPENAPI_SPECS_KEY] = specs
    return app[APP_OPENAPI_SPECS_KEY]

def get_specs(app: web.Application) -> Spec:
    return app[APP_OPENAPI_SPECS_KEY]



Spec = Spec
create_specs = create_specs

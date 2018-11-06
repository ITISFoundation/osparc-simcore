""" rest - Open API specifications


"""

from aiohttp import web

from openapi_core.schema.specs.models import Spec

from .openapi import create_specs
from .application_keys import APP_OPENAPI_SPECS_KEY


def set_specs(app: web.Application, specs: Spec) -> Spec:
    # TODO consider the case of multiple versions of spec -> Dict[Spec] ??
    app[APP_OPENAPI_SPECS_KEY] = specs
    return app[APP_OPENAPI_SPECS_KEY]

def get_specs(app: web.Application) -> Spec:
    # TODO consider the case of multiple versions of spec -> Dict[Spec] ??
    return app[APP_OPENAPI_SPECS_KEY]



OpenApiSpec = Spec
create_specs = create_specs

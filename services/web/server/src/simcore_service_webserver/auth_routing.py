
from .auth_handlers as handlers
from .settings.constants import API_URL_VERSION, APP_OAS_KEY


def map_handlers(router, specs):
    PREFIX = '/' + API_URL_VERSION

    # TODO: this will be done automatically
    path = '/'
    operation_id = specs.paths[path].operations['get'].operation_id
    router.add_route('GET', PREFIX+path, handlers.check_health, name=operation_id)

    path = '/check/{action}'
    operation_id = specs.paths[path].operations['post'].operation_id
    router.add_route('POST', PREFIX+path, handlers.check_action, name=operation_id)


def setup(app):
    validated_spec = app[APP_OAS_KEY]

    map_handlers(validated_spec, app.router)

# these are the apps built right now by static-webserver/client

FRONTEND_APPS_AVAILABLE = frozenset({"osparc", "tis", "s4l", "s4llite", "s4lacad"})
FRONTEND_APP_DEFAULT = "osparc"

assert FRONTEND_APP_DEFAULT in FRONTEND_APPS_AVAILABLE  # nosec


STATIC_DIRNAMES = FRONTEND_APPS_AVAILABLE | {"resource", "transpiled"}

APP_FRONTEND_CACHED_INDEXES_KEY = f"{__name__}.cached_indexes"
APP_FRONTEND_CACHED_STATICS_JSON_KEY = f"{__name__}.cached_statics_json"

APP_CLIENTAPPS_SETTINGS_KEY = f"{__file__}.client_apps_settings"

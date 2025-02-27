from ..constants import FRONTEND_APP_DEFAULT, FRONTEND_APPS_AVAILABLE

STATIC_DIRNAMES = FRONTEND_APPS_AVAILABLE | {"resource", "transpiled"}

APP_FRONTEND_CACHED_INDEXES_KEY = f"{__name__}.cached_indexes"
APP_FRONTEND_CACHED_STATICS_JSON_KEY = f"{__name__}.cached_statics_json"

APP_CLIENTAPPS_SETTINGS_KEY = f"{__file__}.client_apps_settings"


__all__: tuple[str, ...] = (
    "FRONTEND_APPS_AVAILABLE",
    "FRONTEND_APP_DEFAULT",
)

# nopycln: file

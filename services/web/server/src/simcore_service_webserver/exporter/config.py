import trafaret as T
from aiohttp.web import Application
from servicelib.application_keys import APP_CONFIG_KEY

CONFIG_SECTION_NAME = "exporter"

schema = T.Dict(
    {
        T.Key("max_upload_file_size_gb", default=10, optional=False): T.Int(),
        T.Key(
            "downloader_max_timeout_seconds", default=60 * 60, optional=False
        ): T.Int(),
        T.Key("enabled", default=True, optional=False): T.Bool(),
    }
)


def get_max_upload_file_size_gb(app: Application) -> int:
    return int(app[APP_CONFIG_KEY][CONFIG_SECTION_NAME]["max_upload_file_size_gb"])


def get_downloader_max_timeout(app: Application) -> int:
    return int(
        app[APP_CONFIG_KEY][CONFIG_SECTION_NAME]["downloader_max_timeout_seconds"]
    )

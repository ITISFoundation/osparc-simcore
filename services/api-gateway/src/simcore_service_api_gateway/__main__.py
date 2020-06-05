""" Main application entry point

 `python -m simcore_service_api_gateway ...`

"""
import uvicorn

from simcore_service_api_gateway.application import get_settings
from simcore_service_api_gateway.main import the_app
from simcore_service_api_gateway.settings import AppSettings, BootModeEnum


def main():
    settings: AppSettings = get_settings(the_app)
    uvicorn.run(
        the_app,
        host=settings.host,
        port=settings.port,
        reload=settings.boot_mode == BootModeEnum.development,
        log_level=settings.log_level_name.lower(),
    )


if __name__ == "__main__":
    main()

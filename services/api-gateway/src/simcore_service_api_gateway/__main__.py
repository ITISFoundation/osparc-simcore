""" Main application entry point

 `python -m simcore_service_api_gateway ...`

"""
import uvicorn

from simcore_service_api_gateway.core.config import AppSettings, BootModeEnum
from simcore_service_api_gateway.main import the_app


def main():
    cfg: AppSettings = the_app.state.settings
    uvicorn.run(
        the_app,
        host=cfg.host,
        port=cfg.port,
        reload=cfg.boot_mode == BootModeEnum.development,
        log_level=cfg.log_level_name.lower(),
    )


if __name__ == "__main__":
    main()

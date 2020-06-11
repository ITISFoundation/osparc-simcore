""" Main application entry point

 `python -m simcore_service_api_server ...`

"""
import sys
from pathlib import Path

import uvicorn
from fastapi import FastAPI

from simcore_service_api_server.core.application import init_app
from simcore_service_api_server.core.settings import AppSettings, BootModeEnum

current_dir = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent


# SINGLETON FastAPI app
the_app: FastAPI = init_app()


def main():
    cfg: AppSettings = the_app.state.settings
    uvicorn.run(
        the_app,
        host=cfg.host,
        port=cfg.port,
        reload=cfg.boot_mode == BootModeEnum.development,
        reload_dir=current_dir,
        log_level=cfg.log_level_name.lower(),
    )


if __name__ == "__main__":
    main()

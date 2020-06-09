""" Main application entry point

 `python -m simcore_service_api_gateway ...`

"""
import sys
from pathlib import Path

import uvicorn

from simcore_service_api_gateway.core.config import AppSettings, BootModeEnum
from simcore_service_api_gateway.main import the_app

current_dir = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent


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

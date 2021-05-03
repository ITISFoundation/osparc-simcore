import sys
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from simcore_service_dynamic_sidecar.core.application import assemble_application
from simcore_service_dynamic_sidecar.core.settings import DynamicSidecarSettings

current_dir = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent


app: FastAPI = assemble_application()


def main() -> None:
    settings: DynamicSidecarSettings = app.state.settings

    uvicorn.run(
        "simcore_service_dynamic_sidecar.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.is_development_mode,
        reload_dirs=[
            current_dir,
        ],
        log_level=settings.log_level_name.lower(),
    )


if __name__ == "__main__":
    main()

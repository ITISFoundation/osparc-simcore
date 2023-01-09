from typing import Literal

import uvicorn

from .web_application import create_app


def start(
    log_level: Literal["info", "debug", "warning", "error"], reload: bool = False
):
    app = create_app()

    uvicorn.run(
        app=app,
        host="0.0.0.0",
        port=8000,
        log_level=log_level,
        reload=reload,
    )

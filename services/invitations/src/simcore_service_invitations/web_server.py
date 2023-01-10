from typing import Literal

import uvicorn


def start(
    log_level: Literal["info", "debug", "warning", "error"], reload: bool = False
):
    uvicorn.run(
        "simcore_service_invitations.web_main:the_app",
        host="0.0.0.0",
        port=8000,
        log_level=log_level,
        reload=reload,
    )

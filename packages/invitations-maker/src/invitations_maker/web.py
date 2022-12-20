from typing import Literal

import uvicorn
from invitations_maker.web_application import create_app

app = create_app()


def start(log_level: Literal["info", "debug", "warning", "error"] = "info"):
    uvicorn.run(
        "invitations_maker.web:app",
        port=5000,
        log_level=log_level,
    )

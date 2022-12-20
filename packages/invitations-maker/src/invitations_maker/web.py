from typing import Literal

import uvicorn
from fastapi import FastAPI


def create_app() -> FastAPI:
    app = FastAPI()
    return app


def start(log_level: Literal["info", "debug", "warning", "error"] = "info"):
    uvicorn.run(
        "invitations_maker.server:app",
        port=5000,
        log_level=log_level,
    )


if __name__ == "__main__":
    app = create_app()

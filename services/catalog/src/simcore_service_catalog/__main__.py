""" Main application entry point

 `python -m simcore_service_catalog ...`

"""
import uvicorn

from .main import app
from .config import uvicorn_settings


def main():
    uvicorn.run(app, **uvicorn_settings)


if __name__ == "__main__":
    main()

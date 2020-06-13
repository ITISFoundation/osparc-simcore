""" Main application entry point

 `python -m simcore_service_catalog ...`

"""
import uvicorn

from simcore_service_catalog.config import uvicorn_settings
from simcore_service_catalog.main import app


def main():
    uvicorn.run(app, **uvicorn_settings)


if __name__ == "__main__":
    main()

"""Main application to be deployed in for example uvicorn.
"""

from fastapi import FastAPI
from simcore_service_dynamic_sidecar.core.application import create_app

# SINGLETON FastAPI app
the_app: FastAPI = create_app()

"""Main application to be deployed in for example uvicorn
"""

from fastapi import FastAPI
from simcore_service_datcore_adapter.core.application import create_app

# SINGLETON FastAPI app
the_app: FastAPI = create_app()

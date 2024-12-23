"""Main application to be deployed in for example uvicorn.
"""
from fastapi import FastAPI

from .core.application import init_app

# SINGLETON FastAPI app
the_app: FastAPI = init_app()

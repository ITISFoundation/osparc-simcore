"""Only used to initialize uvcorn: ASGI application to run in the format 'module:attribute'
"""
from fastapi import FastAPI
from simcore_service_director_v2.core.application import init_app


# SINGLETON FastAPI app
the_app: FastAPI = init_app()

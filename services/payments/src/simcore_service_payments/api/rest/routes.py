from fastapi import APIRouter, FastAPI, HTTPException

from ..._meta import API_VTAG
from . import _acknowledgements, _auth, _health, _meta
from ._exceptions import handle_errors_as_500, http_exception_as_json_response


def setup_rest_api(app: FastAPI):
    app.include_router(_health.router)

    api_router = APIRouter(prefix=f"/{API_VTAG}")
    api_router.include_router(_auth.router, tags=["auth"])
    api_router.include_router(_meta.router, tags=["meta"])
    api_router.include_router(_acknowledgements.router, tags=["acks"])
    app.include_router(api_router)

    app.add_exception_handler(Exception, handle_errors_as_500)
    app.add_exception_handler(HTTPException, http_exception_as_json_response)

from fastapi import APIRouter
from models_library.api_schemas_storage import HealthCheck
from models_library.app_diagnostics import AppStatusCheck
from models_library.generics import Envelope
from simcore_service_storage._meta import API_VTAG

router = APIRouter(
    prefix=f"/{API_VTAG}",
    tags=[
        "status",
    ],
)


@router.get("/", reponse_model=Envelope[HealthCheck])
async def get_health():
    ...


@router.get("/status", response_model=Envelope[AppStatusCheck])
async def get_status():
    ...

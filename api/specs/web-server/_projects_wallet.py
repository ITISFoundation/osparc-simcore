""" Helper script to automatically generate OAS

This OAS are the source of truth
"""

# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from _common import assert_handler_signature_against_model
from fastapi import APIRouter
from models_library.api_schemas_webserver.wallets import WalletGet
from models_library.generics import Envelope
from models_library.projects import ProjectID
from models_library.wallets import WalletID
from simcore_service_webserver._meta import API_VTAG
from simcore_service_webserver.projects._common_models import ProjectPathParams

router = APIRouter(
    prefix=f"/{API_VTAG}",
    tags=[
        "projects",
    ],
)


@router.get(
    "/projects/{project_id}/wallet",
    response_model=Envelope[WalletGet | None],
    summary="Get current connected wallet to the project.",
)
async def get_project_wallet(project_id: ProjectID):
    ...


assert_handler_signature_against_model(get_project_wallet, ProjectPathParams)


@router.put(
    "/projects/{project_id}/wallet/{wallet_id}",
    response_model=Envelope[WalletGet],
    summary="Connect wallet to the project (Project can have only one wallet)",
)
async def connect_wallet_to_project(
    project_id: ProjectID,
    wallet_id: WalletID,
):
    ...


assert_handler_signature_against_model(connect_wallet_to_project, ProjectPathParams)

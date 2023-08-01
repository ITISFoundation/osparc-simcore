""" Helper script to automatically generate OAS

This OAS are the source of truth
"""

# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from enum import Enum

from _common import (
    CURRENT_DIR,
    assert_handler_signature_against_model,
    create_openapi_specs,
)
from fastapi import FastAPI
from models_library.api_schemas_webserver.wallets import WalletGet
from models_library.generics import Envelope
from models_library.projects import ProjectID
from models_library.wallets import WalletID
from simcore_service_webserver.projects._common_models import ProjectPathParams

app = FastAPI(redoc_url=None)

TAGS: list[str | Enum] = ["project"]


#
# API entrypoints
#


@app.get(
    "/projects/{project_id}/wallet",
    response_model=Envelope[WalletGet | None],
    tags=TAGS,
    operation_id="get_project_wallet",
    summary="Get current connected wallet to the project.",
)
async def get_project_wallet(project_id: ProjectID):
    ...


assert_handler_signature_against_model(get_project_wallet, ProjectPathParams)


@app.put(
    "/projects/{project_id}/wallet/{wallet_id}",
    response_model=Envelope[WalletGet],
    tags=TAGS,
    operation_id="connect_wallet_to_project",
    summary="Connect wallet to the project (Project can have only one wallet)",
)
async def connect_wallet_to_project(
    project_id: ProjectID,
    wallet_id: WalletID,
):
    ...


assert_handler_signature_against_model(connect_wallet_to_project, ProjectPathParams)

if __name__ == "__main__":

    create_openapi_specs(app, CURRENT_DIR.parent / "openapi-projects-wallet.yaml")

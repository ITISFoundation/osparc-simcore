from models_library.api_schemas_webserver.wallets import WalletGet
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.users import UserID
from models_library.wallets import WalletDB, WalletID

from ..wallets import _api as wallet_api
from .db import ProjectDBAPI


async def get_project_wallet(app, project_id: ProjectID):
    db: ProjectDBAPI = ProjectDBAPI.get_from_app_context(app)

    wallet_db: WalletDB | None = await db.get_project_wallet(project_uuid=project_id)
    wallet: WalletGet | None = (
        WalletGet(**wallet_db.model_dump()) if wallet_db else None
    )
    return wallet


async def connect_wallet_to_project(
    app,
    *,
    product_name: ProductName,
    project_id: ProjectID,
    user_id: UserID,
    wallet_id: WalletID,
) -> WalletGet:
    db: ProjectDBAPI = ProjectDBAPI.get_from_app_context(app)

    # ensure the wallet can be used by the user
    wallet: WalletGet = await wallet_api.get_wallet_by_user(
        app,
        user_id=user_id,
        wallet_id=wallet_id,
        product_name=product_name,
    )

    await db.connect_wallet_to_project(project_uuid=project_id, wallet_id=wallet_id)
    return wallet

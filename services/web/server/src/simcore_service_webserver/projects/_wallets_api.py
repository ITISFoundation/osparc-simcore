from models_library.api_schemas_webserver.wallets import WalletGet
from models_library.projects import ProjectID
from models_library.wallets import WalletDB

from .db import ProjectDBAPI


async def get_project_wallet(app, project_id: ProjectID):
    db: ProjectDBAPI = ProjectDBAPI.get_from_app_context(app)

    wallet_db: WalletDB | None = await db.get_project_wallet(project_uuid=project_id)
    wallet: WalletGet | None = WalletGet(**wallet_db.dict()) if wallet_db else None
    return wallet

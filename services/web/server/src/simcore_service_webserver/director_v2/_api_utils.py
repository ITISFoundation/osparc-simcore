from aiohttp import web
from models_library.projects import ProjectID
from models_library.users import UserID
from models_library.wallets import WalletID, WalletInfo
from pydantic import TypeAdapter

from ..application_settings import get_application_settings
from ..products.api import Product
from ..projects import api as projects_api
from ..users import preferences_api as user_preferences_api
from ..users.exceptions import UserDefaultWalletNotFoundError
from ..wallets import api as wallets_api


async def get_wallet_info(
    app: web.Application,
    *,
    product: Product,
    user_id: UserID,
    project_id: ProjectID,
    product_name: str,
) -> WalletInfo | None:
    app_settings = get_application_settings(app)
    if not (
        product.is_payment_enabled and app_settings.WEBSERVER_CREDIT_COMPUTATION_ENABLED
    ):
        return None
    project_wallet = await projects_api.get_project_wallet(app, project_id=project_id)
    if project_wallet is None:
        user_default_wallet_preference = await user_preferences_api.get_frontend_user_preference(
            app,
            user_id=user_id,
            product_name=product_name,
            preference_class=user_preferences_api.PreferredWalletIdFrontendUserPreference,
        )
        if user_default_wallet_preference is None:
            raise UserDefaultWalletNotFoundError(uid=user_id)
        project_wallet_id = TypeAdapter(WalletID).validate_python(
            user_default_wallet_preference.value
        )
        await projects_api.connect_wallet_to_project(
            app,
            product_name=product_name,
            project_id=project_id,
            user_id=user_id,
            wallet_id=project_wallet_id,
        )
    else:
        project_wallet_id = project_wallet.wallet_id

    # Check whether user has access to the wallet
    wallet = await wallets_api.get_wallet_with_available_credits_by_user_and_wallet(
        app,
        user_id=user_id,
        wallet_id=project_wallet_id,
        product_name=product_name,
    )
    return WalletInfo(
        wallet_id=project_wallet_id,
        wallet_name=wallet.name,
        wallet_credit_amount=wallet.available_credits,
    )

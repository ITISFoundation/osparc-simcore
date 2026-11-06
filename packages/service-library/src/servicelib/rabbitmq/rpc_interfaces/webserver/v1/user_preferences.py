"""User preferences RPC API subclient."""

from models_library.products import ProductName
from models_library.user_preferences import FrontendUserPreference
from models_library.users import UserID

from ._base import BaseRpcApi


class UserPreferencesRpcApi(BaseRpcApi):
    """RPC client for frontend user preferences."""

    async def get_frontend_user_preference[PreferenceT: FrontendUserPreference](
        self,
        *,
        product_name: ProductName,
        user_id: UserID,
        preference_class: type[PreferenceT],
    ) -> PreferenceT | None:
        result = await self._request(
            "get_frontend_user_preference",
            product_name=product_name,
            user_id=user_id,
            preference_name=preference_class.get_preference_name(),
        )
        return None if result is None else preference_class.model_validate(result)

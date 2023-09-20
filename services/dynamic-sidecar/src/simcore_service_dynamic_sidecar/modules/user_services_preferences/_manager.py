import logging
from pathlib import Path

from attr import dataclass
from fastapi import FastAPI
from models_library.products import ProductName
from models_library.services import ServiceKey, ServiceVersion
from models_library.users import UserID

from . import _db
from ._utils import is_feature_enabled

_logger = logging.getLogger(__name__)


@dataclass
class UserServicesPreferencesManager:
    user_preferences_path: Path
    service_key: ServiceKey
    service_version: ServiceVersion
    user_id: UserID
    product_name: ProductName
    _preferences_already_saved: bool = False

    async def load_preferences(self) -> None:
        await _db.load_preferences(
            user_preferences_path=self.user_preferences_path,
            service_key=self.service_key,
            service_version=self.service_version,
            user_id=self.user_id,
            product_name=self.product_name,
        )

    async def save_preferences(self) -> None:
        if self._preferences_already_saved:
            _logger.warning("Preferences were already saved, will not save them again")
            return

        await _db.save_preferences(
            user_preferences_path=self.user_preferences_path,
            service_key=self.service_key,
            service_version=self.service_version,
            user_id=self.user_id,
            product_name=self.product_name,
        )

        self._preferences_already_saved = True


async def save_user_services_preferences(app: FastAPI) -> None:
    if not is_feature_enabled(app):
        return

    user_services_preferences_manager: UserServicesPreferencesManager = (
        app.state.user_services_preferences_manager
    )
    await user_services_preferences_manager.save_preferences()


async def load_user_services_preferences(app: FastAPI) -> None:
    if not is_feature_enabled(app):
        return

    user_services_preferences_manager: UserServicesPreferencesManager = (
        app.state.user_services_preferences_manager
    )
    await user_services_preferences_manager.load_preferences()

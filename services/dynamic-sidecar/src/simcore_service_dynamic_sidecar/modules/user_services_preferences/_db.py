from pathlib import Path

import umsgpack  # type: ignore[import-untyped]
from models_library.products import ProductName
from models_library.services import ServiceKey, ServiceVersion
from models_library.user_preferences import PreferenceName
from models_library.users import UserID
from packaging.version import Version
from pydantic import TypeAdapter
from simcore_postgres_database.utils_user_preferences import (
    UserServicesUserPreferencesRepo,
)

# NOTE: Using the same connection pattern to Postgres as the one inside nodeports.
# The same connection context manager is utilized here as well!
from simcore_sdk.node_ports_common.dbmanager import DBContextManager

from ._packaging import dir_from_bytes, dir_to_bytes
from ._user_preference import get_model_class


def _get_db_preference_name(
    preference_name: PreferenceName, service_version: ServiceVersion
) -> str:
    version = Version(service_version)
    return f"{preference_name}/{version.major}.{version.minor}"


async def save_preferences(
    service_key: ServiceKey,
    service_version: ServiceVersion,
    user_preferences_path: Path,
    user_id: UserID,
    product_name: ProductName,
):
    preference_class = get_model_class(service_key)

    dir_content: bytes = await dir_to_bytes(user_preferences_path)
    preference = preference_class(
        service_key=service_key, service_version=service_version, value=dir_content
    )

    async with DBContextManager() as engine, engine.acquire() as conn:
        await UserServicesUserPreferencesRepo.save(
            conn,
            user_id=user_id,
            product_name=product_name,
            preference_name=_get_db_preference_name(
                preference_class.get_preference_name(), service_version
            ),
            payload=umsgpack.packb(preference.to_db()),
        )


async def load_preferences(
    service_key: ServiceKey,
    service_version: ServiceVersion,
    user_preferences_path: Path,
    user_id: UserID,
    product_name: ProductName,
) -> None:
    preference_class = get_model_class(service_key)

    async with DBContextManager() as engine, engine.acquire() as conn:
        payload = await UserServicesUserPreferencesRepo.load(
            conn,
            user_id=user_id,
            product_name=product_name,
            preference_name=_get_db_preference_name(
                preference_class.get_preference_name(), service_version
            ),
        )
    if payload is None:
        return

    preference = TypeAdapter(preference_class).validate_python(
        umsgpack.unpackb(payload)
    )
    await dir_from_bytes(preference.value, user_preferences_path)

import datetime
from typing import Annotated

from aiohttp import web
from pydantic import Field
from servicelib.aiohttp.application_keys import APP_SETTINGS_KEY
from settings_library.base import BaseCustomSettings

from ._itis_vip_settings import ItisVipSettings, SpeagPhantomsSettings


class LicensesSettings(BaseCustomSettings):
    # ITIS - VIP
    LICENSES_ITIS_VIP: Annotated[
        ItisVipSettings | None,
        Field(
            description="Settings for VIP licensed models",
            json_schema_extra={"auto_default_from_env": True},
        ),
    ]
    LICENSES_ITIS_VIP_SYNCER_ENABLED: bool = False
    LICENSES_ITIS_VIP_SYNCER_PERIODICITY: datetime.timedelta = datetime.timedelta(
        days=1
    )

    # SPEAG - PHANTOMS
    LICENSES_SPEAG_PHANTOMS: Annotated[
        SpeagPhantomsSettings | None,
        Field(
            description="Settings for SPEAG licensed phantoms",
            json_schema_extra={"auto_default_from_env": True},
        ),
    ]

    # other licensed resources come here ...


def get_plugin_settings(app: web.Application) -> LicensesSettings:
    settings = app[APP_SETTINGS_KEY].WEBSERVER_LICENSES
    assert settings, "setup_settings not called?"  # nosec
    assert isinstance(settings, LicensesSettings)  # nosec
    return settings

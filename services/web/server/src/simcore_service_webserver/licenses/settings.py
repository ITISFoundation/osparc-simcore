import datetime
from typing import Annotated

from pydantic import Field
from settings_library.base import BaseCustomSettings

from ._itis_vip_settings import ItisVipSettings


class LicensesSettings(BaseCustomSettings):
    LICENSES_SYNCER_ENABLED: bool
    LICENSES_SYNCER_PERIODICITY: datetime.timedelta

    # Registered licensed resources:
    LICENSES_ITIS_VIP: Annotated[
        ItisVipSettings | None, Field(description="Settings for VIP license models")
    ]

    # other licensed resources come here ...

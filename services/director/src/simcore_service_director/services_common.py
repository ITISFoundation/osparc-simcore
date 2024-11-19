#
# Taken from packages/models-library/src/models_library/settings/services_common.py
# since this service is frozen and MUST NOT ADD ANY MORE DEPENDENCIES
#
#
from pydantic import Field, PositiveInt
from pydantic_settings import BaseSettings, SettingsConfigDict

_BASE_TIMEOUT_FOR_STOPPING_SERVICES = 60 * 60


class ServicesCommonSettings(BaseSettings):
    # set this interval to 1 hour
    director_dynamic_service_save_timeout: PositiveInt = Field(
        default=_BASE_TIMEOUT_FOR_STOPPING_SERVICES,
        description=(
            "When stopping a dynamic service, if it has "
            "big payloads it is important to have longer timeouts."
        ),
    )
    webserver_director_stop_service_timeout: PositiveInt = Field(
        default=_BASE_TIMEOUT_FOR_STOPPING_SERVICES + 10,
        description=(
            "When the webserver invokes the director API to stop "
            "a service which has a very long timeout, it also "
            "requires to wait that amount plus some extra padding."
        ),
    )
    storage_service_upload_download_timeout: PositiveInt = Field(
        default=60 * 60,
        description=(
            "When dynamic services upload and download data from storage, "
            "sometimes very big payloads are involved. In order to handle "
            "such payloads it is required to have long timeouts which "
            "allow the service to finish the operation."
        ),
    )
    model_config = SettingsConfigDict(
        env_prefix="SERVICES_COMMON_", case_sensitive=False
    )

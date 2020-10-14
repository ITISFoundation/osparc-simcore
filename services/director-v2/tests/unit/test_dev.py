# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


import httpx
from simcore_service_director_v2.core.settings import AppSettings, RegistrySettings


def test_it(project_env_devel_environment):

    settings: RegistrySettings = AppSettings.create_from_env().registry

    with httpx.Client(base_url=settings.api_url) as client:
        r = client.get("/_catalog")
        print(r.json())

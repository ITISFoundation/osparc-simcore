import osparc
import json
from typing import Optional

_config: Optional[osparc.Configuration] = None    
    
def init_session(username: str, password: str) -> None:
    """
    Configure a session
    """
    global _config
    _config = osparc.Configuration(
        username=username,
        password=password
    )
    # validate credentials
    try:
        with osparc.ApiClient(_config) as api_client:
            users_api = osparc.UsersApi(api_client)
            users_api.get_my_profile()
    except osparc.exceptions.ApiException as e:
        api_client.close()
        expt = json.loads(e.body)
        raise Exception('\n'.join(expt["errors"])) from None
    

def get_config() -> osparc.Configuration:
    """
    Get current configuration.
    """
    global _config
    if _config is None:
        raise ValueError("Session has not yet been configured. Call 'init_session' to configure a session")
    return _config
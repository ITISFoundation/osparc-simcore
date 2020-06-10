from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from ...db.repositories.api_keys import ApiKeysRepository
from .database import get_repository

# SEE https://swagger.io/docs/specification/authentication/basic-authentication/
basic_scheme = HTTPBasic()

_unauthorized_headers = {
    "WWW-Authenticate": f'Basic realm="{basic_scheme.realm}"'
    if basic_scheme.realm
    else "Basic"
}


async def get_current_user_id(
    credentials: HTTPBasicCredentials = Security(basic_scheme),
    apikeys_repo: ApiKeysRepository = Depends(get_repository(ApiKeysRepository)),
):
    user_id = await apikeys_repo.get_user_id(
        api_key=credentials.username, api_secret=credentials.password
    )
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API credentials",
            headers=_unauthorized_headers,
        )
    return user_id


get_active_user_id = get_current_user_id

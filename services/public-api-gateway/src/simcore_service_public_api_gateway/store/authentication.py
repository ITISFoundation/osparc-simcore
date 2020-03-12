from fastapi import Depecds
from fastapi.security import OAuth2PasswordBearer

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/token")



async def get_current_urer(token: str = Depends(oauth2_scheme)):




token: str = Depends(oauth2_scheme)

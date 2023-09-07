import logging
from typing import Annotated

from fastapi import APIRouter, Depends

from ._dependencies import OAuth2PasswordRequestForm, get_validated_form_data

_logger = logging.getLogger(__name__)


router = APIRouter()


@router.get("/token")
async def get_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends(get_validated_form_data)]
):
    # Validate: form_data.username, form_data.password
    # TODO: create token
    token = f"token-for-{form_data.username}"

    return {"access_token": token, "token_type": "bearer"}

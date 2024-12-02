from typing import Annotated

from fastapi import APIRouter, Depends, status
from models_library.api_schemas_webserver.auth import ApiKeyCreate, ApiKeyGet
from models_library.generics import Envelope
from models_library.rest_error import EnvelopedError
from simcore_service_webserver._meta import API_VTAG
from simcore_service_webserver.api_keys._exceptions_handlers import _TO_HTTP_ERROR_MAP
from simcore_service_webserver.api_keys._models import ApiKeysPathParams

router = APIRouter(
    prefix=f"/{API_VTAG}",
    tags=["auth"],
    responses={
        i.status_code: {"model": EnvelopedError} for i in _TO_HTTP_ERROR_MAP.values()
    },
)


@router.post(
    "/auth/api-keys",
    operation_id="create_api_key",
    status_code=status.HTTP_201_CREATED,
    response_model=Envelope[ApiKeyGet],
    # responses={
    #     status.HTTP_200_OK: {
    #         "description": "Authorization granted returning API key",
    #         "model": ApiKeyGet,
    #     },
    #     status.HTTP_400_BAD_REQUEST: {
    #         "description": "key name requested is invalid",
    #     },
    #     status.HTTP_401_UNAUTHORIZED: {
    #         "description": "requires login to  list keys",
    #     },
    #     status.HTTP_403_FORBIDDEN: {
    #         "description": "not enough permissions to list keys",
    #     },
    # },
)
async def create_api_key(_body: ApiKeyCreate):
    """creates API keys to access public API"""


@router.get(
    "/auth/api-keys",
    operation_id="list_display_names",
    response_model=Envelope[list[str]],
    # responses={
    #     status.HTTP_200_OK: {
    #         "description": "returns the display names of API keys",
    #         "model": list[str],
    #     },
    #     status.HTTP_400_BAD_REQUEST: {
    #         "description": "key name requested is invalid",
    #     },
    #     status.HTTP_401_UNAUTHORIZED: {
    #         "description": "requires login to  list keys",
    #     },
    #     status.HTTP_403_FORBIDDEN: {
    #         "description": "not enough permissions to list keys",
    #     },
    # },
)
async def list_api_keys():
    """lists display names of API keys by this user"""


@router.get(
    "/auth/api-keys/{api_key_id}",
    operation_id="get_api_key",
    response_model=Envelope[ApiKeyGet],
    # responses={
    #     status.HTTP_200_OK: {
    #         "description": "returns the api key or None",
    #         "model": ApiKeyGet | None,
    #     },
    #     status.HTTP_400_BAD_REQUEST: {
    #         "description": "key name requested is invalid",
    #     },
    #     status.HTTP_401_UNAUTHORIZED: {
    #         "description": "requires login to get the keu",
    #     },
    #     status.HTTP_403_FORBIDDEN: {
    #         "description": "not enough permissions to get the keu",
    #     },
    # },
)
async def get_api_key(_path: Annotated[ApiKeysPathParams, Depends()]):
    """returns the key or None"""


@router.delete(
    "/auth/api-keys",
    operation_id="delete_api_key",
    status_code=status.HTTP_204_NO_CONTENT,
    # responses={
    #     status.HTTP_204_NO_CONTENT: {
    #         "description": "api key successfully deleted",
    #     },
    #     status.HTTP_401_UNAUTHORIZED: {
    #         "description": "requires login to  delete a key",
    #     },
    #     status.HTTP_403_FORBIDDEN: {
    #         "description": "not enough permissions to delete a key",
    #     },
    # },
)
async def delete_api_key(_body: ApiKeyCreate):
    """deletes API key by name"""

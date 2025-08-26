"""Service interface for user tokens operations"""

from aiohttp import web
from models_library.users import UserID, UserThirdPartyToken

from ._repository import UserTokensRepository


async def list_tokens(
    app: web.Application, user_id: UserID
) -> list[UserThirdPartyToken]:
    """List all tokens for a user"""
    repo = UserTokensRepository.create_from_app(app)
    return await repo.list_tokens(user_id=user_id)


async def create_token(
    app: web.Application, *, user_id: UserID, token: UserThirdPartyToken
) -> UserThirdPartyToken:
    """Create a new token for a user"""
    repo = UserTokensRepository.create_from_app(app)
    return await repo.create_token(user_id=user_id, token=token)


async def get_token(
    app: web.Application, *, user_id: UserID, service_id: str
) -> UserThirdPartyToken:
    """Get a specific token for a user and service"""
    repo = UserTokensRepository.create_from_app(app)
    return await repo.get_token(user_id=user_id, service_id=service_id)


async def delete_token(
    app: web.Application, *, user_id: UserID, service_id: str
) -> None:
    """Delete a token for a user and service"""
    repo = UserTokensRepository.create_from_app(app)
    await repo.delete_token(user_id=user_id, service_id=service_id)

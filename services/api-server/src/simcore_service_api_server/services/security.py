""" Utility functions related with security

"""

from passlib.context import CryptContext

# from .models.schemas.users import UserInDB

# PASSWORDS ---------------------------------------------------------------

__pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return __pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return __pwd_context.hash(password)


# def authenticate_user(username: str, password: str) -> Optional[UserInDB]:
#     user = crud.get_user(username)
#     if not user:
#         return None
#     if not verify_password(password, user.hashed_password):
#         return None
#     return user

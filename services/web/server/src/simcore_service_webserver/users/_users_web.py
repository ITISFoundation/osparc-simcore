import logging
from typing import Literal, TypedDict

from aiohttp_session import Session
from models_library.users import UserID
from servicelib.aiohttp import status

from .exceptions import (
    PhoneRegistrationCodeInvalidError,
    PhoneRegistrationPendingNotFoundError,
    PhoneRegistrationSessionInvalidError,
)

_logger = logging.getLogger(__name__)

# Registration session keys
_REGISTRATION_KEY = "registration"
_REGISTRATION_PENDING_KEY = "registration_pending"
_REGISTRATION_CODE_KEY = "registration_code"


class RegistrationData(TypedDict):
    """Registration session data structure."""

    user_id: UserID
    data: str
    status: Literal["pending_confirmation"]


class RegistrationSessionManager:
    def __init__(self, session: Session, user_id: UserID, product_name: str):
        self._session = session
        self._user_id = user_id
        self._product_name = product_name

    def start_registration(self, data: str, code: str) -> None:
        registration_data: RegistrationData = {
            "user_id": self._user_id,
            "data": data,  # keep data
            "status": "pending_confirmation",
        }
        self._session[_REGISTRATION_KEY] = registration_data
        self._session[_REGISTRATION_CODE_KEY] = code
        self._session[_REGISTRATION_PENDING_KEY] = True

    def validate_pending_registration(self) -> RegistrationData:
        if not self._session.get(_REGISTRATION_PENDING_KEY):
            raise PhoneRegistrationPendingNotFoundError(
                user_id=self._user_id, product_name=self._product_name
            )

        registration: RegistrationData | None = self._session.get(_REGISTRATION_KEY)
        if not registration or registration["user_id"] != self._user_id:
            raise PhoneRegistrationSessionInvalidError(
                user_id=self._user_id, product_name=self._product_name
            )

        return registration

    def regenerate_code(self, new_code: str) -> None:
        self.validate_pending_registration()
        self._session[_REGISTRATION_CODE_KEY] = new_code

    def validate_confirmation_code(self, provided_code: str) -> None:
        expected_code = self._session.get(_REGISTRATION_CODE_KEY)
        if not expected_code or provided_code != expected_code:
            raise PhoneRegistrationCodeInvalidError(
                user_id=self._user_id, product_name=self._product_name
            )

    def clear_session(self) -> None:
        self._session.pop(_REGISTRATION_KEY, None)
        self._session.pop(_REGISTRATION_PENDING_KEY, None)
        self._session.pop(_REGISTRATION_CODE_KEY, None)

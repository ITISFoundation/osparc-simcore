"""Helper functions for creating notification data models."""

from models_library.emails import LowerCaseEmailStr
from notifications_library._models import UserData


def create_user_data(
    *,
    user_email: LowerCaseEmailStr,
    first_name: str,
    last_name: str,
) -> UserData:
    return UserData(
        user_name=f"{first_name} {last_name}".strip(),
        email=user_email,
        first_name=first_name,
        last_name=last_name,
    )

# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "httpx",
# ]
# ///

from typing import Any

from httpx import AsyncClient
from pydantic import BaseModel, EmailStr, SecretStr


class LoginCredentials(BaseModel):
    """Request body model for login endpoint"""

    email: EmailStr
    password: SecretStr


class PreRegisterUserRequest(BaseModel):
    """Request body model for pre-registering a user"""

    firstName: str
    lastName: str
    email: EmailStr
    phone: str | None = None
    address: str | None = None
    city: str | None = None
    postalCode: str | None = None
    country: str | None = None


class PreRegisterUserResponse(BaseModel):
    """Response model for pre-registered user"""

    firstName: str
    lastName: str
    email: EmailStr
    phone: str | None = None
    address: str | None = None
    city: str | None = None
    postalCode: str | None = None
    country: str | None = None


class InvitationGenerateRequest(BaseModel):
    """Request body model for generating an invitation"""

    guest: EmailStr


class InvitationGenerated(BaseModel):
    """Response model for generated invitation"""

    productName: str
    issuer: str
    guest: EmailStr
    created: str
    invitationLink: str


async def logout_current_user(client: AsyncClient):
    path = "/auth/logout"
    r = await client.post(path)
    r.raise_for_status()


async def login(
    client: AsyncClient, email: EmailStr, password: SecretStr
) -> dict[str, Any]:
    """Login user with the provided credentials

    Args:
        client: The HTTP client to use for API requests
        email: User's email
        password: User's password

    Returns:
        Dict containing login response data

    Raises:
        HTTPStatusError: If the login request fails
    """
    path = "/v0/auth/login"

    credentials = LoginCredentials(email=email, password=password)

    response = await client.post(
        path, json=credentials.model_dump(exclude_none=True, mode="json")
    )
    response.raise_for_status()

    return response.json()["data"]


async def pre_register_user(
    client: AsyncClient,
    first_name: str,
    last_name: str,
    email: EmailStr,
    phone: str | None = None,
    address: str | None = None,
    city: str | None = None,
    postal_code: str | None = None,
    country: str | None = None,
) -> PreRegisterUserResponse:
    """Pre-register a user in the system

    Args:
        client: The HTTP client to use for API requests
        first_name: User's first name
        last_name: User's last name
        email: User's email
        phone: User's phone number (optional)
        address: User's address (optional)
        city: User's city (optional)
        postal_code: User's postal code (optional)
        country: User's country (optional)

    Returns:
        PreRegisterUserResponse containing the pre-registered user data

    Raises:
        HTTPStatusError: If the pre-registration request fails
    """
    path = "/v0/admin/users:pre-register"

    user_data = PreRegisterUserRequest(
        firstName=first_name,
        lastName=last_name,
        email=email,
        phone=phone,
        address=address,
        city=city,
        postalCode=postal_code,
        country=country,
    )

    response = await client.post(
        path, json=user_data.model_dump(exclude_none=True, mode="json")
    )
    response.raise_for_status()

    return PreRegisterUserResponse(**response.json()["data"])


async def generate_invitation(
    client: AsyncClient, guest_email: EmailStr
) -> InvitationGenerated:
    """Generate an invitation link for a guest email

    Args:
        client: The HTTP client to use for API requests
        guest_email: Email address of the guest to invite

    Returns:
        InvitationGenerated containing the invitation details and link

    Raises:
        HTTPStatusError: If the invitation generation request fails
    """
    path = "/v0/invitation:generate"

    invitation_data = InvitationGenerateRequest(guest=guest_email)

    response = await client.post(
        path, json=invitation_data.model_dump(exclude_none=True, mode="json")
    )
    response.raise_for_status()

    return InvitationGenerated(**response.json()["data"])

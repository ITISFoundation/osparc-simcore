# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "httpx",
#     "pydantic",
#     "typer",
# ]
# ///

from typing import Annotated, Any

from httpx import AsyncClient
from pydantic import BaseModel, EmailStr, Field, SecretStr


class LoginCredentials(BaseModel):
    """Request body model for login endpoint"""

    email: EmailStr
    password: SecretStr


# TODO: move classes to models-library from webserver and use them here
class PreRegisterUserRequest(BaseModel):
    """Request body model for pre-registering a user"""

    firstName: str
    lastName: str
    email: EmailStr
    instititution: str | None = None
    phone: str | None = None
    address: str | None = None
    city: str | None = None
    state: Annotated[str | None, Field(description="State, province, canton, ...")]
    postalCode: str | None = None
    country: str | None = None
    extras: dict[str, Any] = {}


class PreRegisterUserResponse(BaseModel):
    """Response model for pre-registered user"""

    # ONLY for admins
    firstName: str | None
    lastName: str | None
    email: EmailStr
    institution: str | None
    phone: str | None
    address: str | None
    city: str | None
    state: Annotated[str | None, Field(description="State, province, canton, ...")]
    postal_code: str | None
    country: str | None
    extras: dict[str, Any] = {}

    # authorization
    invited_by: str | None = None


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


async def logout_current_user(client: AsyncClient):
    path = "/auth/logout"
    r = await client.post(path)
    r.raise_for_status()


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

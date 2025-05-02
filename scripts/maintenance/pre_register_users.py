# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "httpx",
#     "pydantic",
#     "typer",
# ]
# ///

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Annotated, Any

import typer
from httpx import AsyncClient
from pydantic import BaseModel, EmailStr, Field, SecretStr, TypeAdapter, ValidationError


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
    institution: str | None = None,
    phone: str | None = None,
    address: str | None = None,
    city: str | None = None,
    state: str | None = None,
    postal_code: str | None = None,
    country: str | None = None,
    extras: dict[str, Any] = {},
) -> PreRegisterUserResponse:
    """Pre-register a user in the system

    Args:
        client: The HTTP client to use for API requests
        first_name: User's first name
        last_name: User's last name
        email: User's email
        institution: User's institution (optional)
        phone: User's phone number (optional)
        address: User's address (optional)
        city: User's city (optional)
        state: User's state, province, or canton (optional)
        postal_code: User's postal code (optional)
        country: User's country (optional)
        extras: Additional user information (optional)

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
        instititution=institution,
        phone=phone,
        address=address,
        city=city,
        state=state,
        postalCode=postal_code,
        country=country,
        extras=extras,
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


async def pre_register_users_from_file(
    client: AsyncClient,
    users_data: list[PreRegisterUserRequest],
) -> list[PreRegisterUserResponse]:
    """Pre-registers multiple users from a list of user data

    Args:
        client: The HTTP client to use for API requests
        users_data: List of user data to pre-register

    Returns:
        List of pre-registered user responses
    """
    results = []
    for user_data in users_data:
        try:
            result = await pre_register_user(
                client=client,
                first_name=user_data.firstName,
                last_name=user_data.lastName,
                email=user_data.email,
                institution=user_data.instititution,
                phone=user_data.phone,
                address=user_data.address,
                city=user_data.city,
                state=user_data.state,
                postal_code=user_data.postalCode,
                country=user_data.country,
                extras=user_data.extras,
            )
            results.append(result)
            typer.secho(
                f"Successfully pre-registered user: {user_data.email}",
                fg=typer.colors.GREEN,
            )
        except Exception as e:
            typer.secho(
                f"Failed to pre-register user {user_data.email}: {str(e)}",
                fg=typer.colors.RED,
                err=True,
            )

    return results


async def run_pre_registration(
    base_url: str,
    users_file_path: Path,
    admin_email: str,
    admin_password: str,
) -> None:
    """Run the pre-registration process

    Args:
        base_url: Base URL of the API
        users_file_path: Path to the JSON file containing user data
        admin_email: Admin email for login
        admin_password: Admin password for login
    """
    # Read and parse the users file
    try:
        users_data_raw = json.loads(users_file_path.read_text())
        users_data = TypeAdapter(list[PreRegisterUserRequest]).validate_python(
            users_data_raw
        )
    except json.JSONDecodeError:
        typer.secho(
            f"Error: {users_file_path} is not a valid JSON file",
            fg=typer.colors.RED,
            err=True,
        )
        sys.exit(os.EX_DATAERR)
    except ValidationError as e:
        typer.secho(
            f"Error: Invalid user data format: {e}", fg=typer.colors.RED, err=True
        )
        sys.exit(os.EX_DATAERR)
    except Exception as e:
        typer.secho(
            f"Error reading or parsing {users_file_path}: {str(e)}",
            fg=typer.colors.RED,
            err=True,
        )
        sys.exit(os.EX_IOERR)

    # Create an HTTP client
    async with AsyncClient(base_url=base_url, timeout=30) as client:
        try:
            # Login as admin
            typer.secho(f"Logging in as {admin_email}...", fg=typer.colors.BLUE)
            await login(
                client=client,
                email=EmailStr(admin_email),
                password=SecretStr(admin_password),
            )

            # Pre-register users
            typer.secho(
                f"Pre-registering {len(users_data)} users...", fg=typer.colors.BLUE
            )
            results = await pre_register_users_from_file(client, users_data)
            typer.secho(
                f"Successfully pre-registered {len(results)} users",
                fg=typer.colors.GREEN,
            )

            # Logout
            typer.secho("Logging out...", fg=typer.colors.BLUE)
            await logout_current_user(client)

        except Exception as e:
            typer.secho(f"Error: {str(e)}", fg=typer.colors.RED, err=True)
            sys.exit(os.EX_SOFTWARE)


app = typer.Typer(help="Pre-register users in osparc-simcore")


@app.command()
def pre_register(
    users_file: Annotated[
        Path,
        typer.Argument(help="Path to JSON file containing user data to pre-register"),
    ],
    base_url: Annotated[
        str,
        typer.Option(
            "--base-url",
            "-u",
            help="Base URL of the API",
        ),
    ] = "http://localhost:8001",
    admin_email: Annotated[
        str,
        typer.Option(
            "--email",
            "-e",
            help="Admin email for login",
        ),
    ] = None,
    admin_password: Annotated[
        str,
        typer.Option(
            "--password",
            "-p",
            help="Admin password for login",
            prompt=True,
            hide_input=True,
        ),
    ] = None,
):
    """Pre-register users from a JSON file.

    The JSON file should contain a list of user objects with the following fields:
    firstName, lastName, email, and optionally institution, phone, address, city, state, postalCode, country.
    """
    if not users_file.exists():
        typer.secho(
            f"Error: File {users_file} does not exist", fg=typer.colors.RED, err=True
        )
        raise typer.Exit(code=os.EX_NOINPUT)

    if not admin_email:
        admin_email = typer.prompt("Admin email")

    typer.secho(
        f"Pre-registering users from {users_file} using {base_url}",
        fg=typer.colors.BLUE,
    )
    asyncio.run(run_pre_registration(base_url, users_file, admin_email, admin_password))
    typer.secho("Pre-registration completed", fg=typer.colors.GREEN)


if __name__ == "__main__":
    app()

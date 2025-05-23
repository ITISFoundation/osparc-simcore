# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "httpx",
#     "pydantic[email]",
#     "typer",
# ]
# ///
"""
Examples of usage:
    $ uv run pre_registration.py --help

    $ uv run pre_registration.py pre-register pre_register_users.json --base-url http://localhost:8001 --email admin@email.com

    $ uv run pre_registration.py invite user@example.com --base-url http://localhost:8001 --email admin@email.com

    $ uv run pre_registration.py invite-all users.json --base-url http://localhost:8001 --email admin@email.com
"""

import asyncio
import datetime
import json
import os
import sys
from pathlib import Path
from typing import Annotated, Any

import typer
from httpx import AsyncClient, HTTPStatusError
from pydantic import (
    BaseModel,
    BeforeValidator,
    EmailStr,
    Field,
    PositiveInt,
    SecretStr,
    TypeAdapter,
    ValidationError,
)


def _print_info(message: str) -> None:
    typer.secho(message, fg=typer.colors.BLUE)


def _print_success(message: str) -> None:
    typer.secho(message, fg=typer.colors.GREEN)


def _print_error(message: str) -> None:
    typer.secho(f"Error: {message}", fg=typer.colors.RED, err=True)


class LoginCredentialsRequest(BaseModel):
    """Request body model for login endpoint"""

    email: EmailStr
    password: SecretStr


class PreRegisterUserRequest(BaseModel):
    """Request body model for pre-registering a user"""

    firstName: str
    lastName: str
    email: EmailStr
    institution: str | None = None
    phone: str | None = None
    address: str | None = None
    city: str | None = None
    state: Annotated[str | None, Field(description="State, province, canton, ...")]
    postalCode: str | None = None
    country: str | None = None
    extras: dict[str, Any] = {}


class InvitationGenerateRequest(BaseModel):
    """Request body model for generating an invitation"""

    guest: EmailStr
    trialAccountDays: PositiveInt | None = None
    extraCreditsInUsd: Annotated[int, Field(ge=0, lt=500)] | None = None


async def _login(
    client: AsyncClient, email: EmailStr, password: SecretStr
) -> dict[str, Any]:
    """Login user with the provided credentials"""
    path = "/v0/auth/login"

    credentials = LoginCredentialsRequest(email=email, password=password)

    response = await client.post(
        path,
        json={
            "email": credentials.email,
            "password": credentials.password.get_secret_value(),
        },
    )
    response.raise_for_status()

    return response.json()["data"]


async def _logout_current_user(client: AsyncClient):
    path = "/v0/auth/logout"
    r = await client.post(path)
    r.raise_for_status()


async def _pre_register_user(
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
) -> dict[str, Any]:
    """Pre-register a user in the system"""
    path = "/v0/admin/user-accounts:pre-register"

    user_data = PreRegisterUserRequest(
        firstName=first_name,
        lastName=last_name,
        email=email,
        institution=institution,
        phone=phone,
        address=address or "",
        city=city or "",
        state=state,
        postalCode=postal_code or "",
        country=country,
        extras=extras,
    )

    response = await client.post(path, json=user_data.model_dump(mode="json"))
    response.raise_for_status()

    return response.json()["data"]


async def _create_invitation(
    client: AsyncClient,
    guest_email: EmailStr,
    trial_days: PositiveInt | None = None,
    extra_credits: int | None = None,
) -> dict[str, Any]:
    """Generate an invitation link for a guest email"""
    path = "/v0/invitation:generate"

    invitation_data = InvitationGenerateRequest(
        guest=guest_email,
        trialAccountDays=trial_days,
        extraCreditsInUsd=extra_credits,
    )

    response = await client.post(
        path,
        json=invitation_data.model_dump(
            exclude_none=True, exclude_unset=True, mode="json"
        ),
    )
    response.raise_for_status()

    return response.json()["data"]


async def _pre_register_users_from_list(
    client: AsyncClient,
    users_data: list[PreRegisterUserRequest],
) -> list[dict[str, Any]]:
    """Pre-registers multiple users from a list of user data"""
    results = []
    for user_data in users_data:
        try:
            result = await _pre_register_user(
                client=client,
                first_name=user_data.firstName,
                last_name=user_data.lastName,
                email=user_data.email,
                institution=user_data.institution,
                phone=user_data.phone,
                address=user_data.address,
                city=user_data.city,
                state=user_data.state,
                postal_code=user_data.postalCode,
                country=user_data.country,
                extras=user_data.extras,
            )
            results.append(result)
            _print_success(f"Successfully pre-registered user: {user_data.email}")

        except HTTPStatusError as e:
            _print_error(
                f"Failed to pre-register user {user_data.email} with {e.response.status_code}: {e.response.text}"
            )

        except Exception as e:
            _print_error(f"Failed to pre-register user {user_data.email}: {str(e)}")

    return results


async def _create_invitations_from_list(
    client: AsyncClient,
    emails: list[EmailStr],
    trial_days: PositiveInt | None = None,
    extra_credits: int | None = None,
) -> list[dict[str, Any]]:
    """Generate invitations for multiple users from a list of emails"""
    results = []
    for email in emails:
        try:
            result = await _create_invitation(
                client=client,
                guest_email=email,
                trial_days=trial_days,
                extra_credits=extra_credits,
            )
            results.append({"email": email, "invitation": result})
            _print_success(f"Successfully generated invitation for: {email}")

        except HTTPStatusError as e:
            _print_error(
                f"Failed to generate invitation for {email} with {e.response.status_code}: {e.response.text}"
            )
            results.append({"email": email, "error": str(e)})

        except Exception as e:
            _print_error(f"Failed to generate invitation for {email}: {str(e)}")
            results.append({"email": email, "error": str(e)})

    return results


async def run_pre_registration(
    base_url: str,
    users_file_path: Path,
    admin_email: str,
    admin_password: str,
) -> None:
    """Run the pre-registration process"""
    # Read and parse the users file
    try:
        users_data_raw = json.loads(users_file_path.read_text())
        users_data = TypeAdapter(list[PreRegisterUserRequest]).validate_python(
            users_data_raw
        )
    except json.JSONDecodeError:
        _print_error(f"{users_file_path} is not a valid JSON file")
        sys.exit(os.EX_DATAERR)
    except ValidationError as e:
        _print_error(f"Invalid user data format: {e}")
        sys.exit(os.EX_DATAERR)
    except Exception as e:
        _print_error(f"Reading or parsing {users_file_path}: {str(e)}")
        sys.exit(os.EX_IOERR)

    # Create an HTTP client and process
    async with AsyncClient(base_url=base_url, timeout=30) as client:
        try:
            # Login as admin
            _print_info(f"Logging in as {admin_email}...")
            await _login(
                client=client,
                email=admin_email,
                password=admin_password,
            )

            # Pre-register users
            _print_info(f"Pre-registering {len(users_data)} users...")
            results = await _pre_register_users_from_list(client, users_data)
            _print_success(f"Successfully pre-registered {len(results)} users")

            # Dump results to a file
            timestamp = datetime.datetime.now(tz=datetime.UTC).strftime("%Y%m%d_%H%M%S")
            input_filename = users_file_path.stem
            output_filename = f"{input_filename}_results_{timestamp}.json"
            output_path = users_file_path.parent / output_filename

            output_path.write_text(json.dumps(results, indent=1))
            _print_success(f"Results written to {output_path}")

            # Logout
            _print_info("Logging out...")
            await _logout_current_user(client)

        except Exception as e:
            _print_error(f"{str(e)}")
            sys.exit(os.EX_SOFTWARE)


async def run_create_invitation(
    base_url: str,
    guest_email: EmailStr,
    admin_email: str,
    admin_password: str,
    trial_days: PositiveInt | None = None,
    extra_credits: int | None = None,
) -> None:
    """Run the invitation generation process"""
    async with AsyncClient(base_url=base_url, timeout=30) as client:
        try:
            # Login as admin
            _print_info(f"Logging in as {admin_email}...")
            await _login(
                client=client,
                email=admin_email,
                password=admin_password,
            )

            # Generate invitation
            _print_info(f"Generating invitation for {guest_email}...")
            result = await _create_invitation(
                client, guest_email, trial_days=trial_days, extra_credits=extra_credits
            )

            # Display invitation link
            _print_success(f"Successfully generated invitation for {guest_email}")
            _print_success(f"Invitation link: {result.get('link', 'No link returned')}")

            # Save result to a file
            timestamp = datetime.datetime.now(tz=datetime.UTC).strftime("%Y%m%d_%H%M%S")
            output_filename = f"invitation_{guest_email.split('@')[0]}_{timestamp}.json"
            output_path = Path(output_filename)
            output_path.write_text(json.dumps(result, indent=1))
            _print_success(f"Result written to {output_path}")

            # Logout
            _print_info("Logging out...")
            await _logout_current_user(client)

        except HTTPStatusError as e:
            _print_error(
                f"Failed to generate invitation with {e.response.status_code}: {e.response.text}"
            )
            sys.exit(os.EX_SOFTWARE)
        except Exception as e:
            _print_error(f"{str(e)}")
            sys.exit(os.EX_SOFTWARE)


async def run_bulk_create_invitation(
    base_url: str,
    emails_file_path: Path,
    admin_email: str,
    admin_password: str,
    trial_days: PositiveInt | None = None,
    extra_credits: int | None = None,
) -> None:
    """Run the bulk invitation process"""
    # Read and parse the emails file
    try:
        file_content = emails_file_path.read_text()
        data = json.loads(file_content)

        # Check if the file contains a list of emails or objects with email property
        if isinstance(data, list):
            if all(isinstance(item, str) for item in data):
                # Simple list of email strings
                data = data
            elif all(isinstance(item, dict) and "email" in item for item in data):
                # List of objects with email property (like pre-registered users)
                data = [item["email"].lower() for item in data]
            else:
                _print_error(
                    "File must contain either a list of email strings or objects with 'email' property"
                )
                sys.exit(os.EX_DATAERR)

            emails = TypeAdapter(
                list[Annotated[BeforeValidator(lambda s: s.lower()), EmailStr]]
            ).validate_python(data)
        else:
            _print_error("File must contain a JSON array")
            sys.exit(os.EX_DATAERR)

    except json.JSONDecodeError:
        _print_error(f"{emails_file_path} is not a valid JSON file")
        sys.exit(os.EX_DATAERR)
    except ValidationError as e:
        _print_error(f"Invalid email format: {e}")
        sys.exit(os.EX_DATAERR)
    except Exception as e:
        _print_error(f"Reading or parsing {emails_file_path}: {str(e)}")
        sys.exit(os.EX_IOERR)

    # Create an HTTP client and process
    async with AsyncClient(base_url=base_url, timeout=30) as client:
        try:
            # Login as admin
            _print_info(f"Logging in as {admin_email}...")
            await _login(
                client=client,
                email=admin_email,
                password=admin_password,
            )

            # Generate invitations
            _print_info(f"Generating invitations for {len(emails)} users...")
            results = await _create_invitations_from_list(
                client, emails, trial_days=trial_days, extra_credits=extra_credits
            )

            successful = sum(1 for r in results if "invitation" in r)
            _print_success(
                f"Successfully generated {successful} invitations out of {len(emails)} users"
            )

            # Dump results to a file
            timestamp = datetime.datetime.now(tz=datetime.UTC).strftime("%Y%m%d_%H%M%S")
            input_filename = emails_file_path.stem
            output_filename = f"{input_filename}_invitations_{timestamp}.json"
            output_path = emails_file_path.parent / output_filename

            output_path.write_text(json.dumps(results, indent=1))
            _print_success(f"Results written to {output_path}")

            # Logout
            _print_info("Logging out...")
            await _logout_current_user(client)

        except Exception as e:
            _print_error(f"{str(e)}")
            sys.exit(os.EX_SOFTWARE)


# Create Typer app with common options
app = typer.Typer(help="User management utilities for osparc-simcore")

# Common options
BaseUrlOption = Annotated[
    str,
    typer.Option(
        "--base-url",
        "-u",
        help="Base URL of the API",
    ),
]

AdminEmailOption = Annotated[
    str,
    typer.Option(
        "--email",
        "-e",
        help="Admin email for login",
    ),
]

AdminPasswordOption = Annotated[
    str,
    typer.Option(
        "--password",
        "-p",
        help="Admin password for login",
        prompt=True,
        hide_input=True,
    ),
]


@app.command()
def pre_register(
    users_file: Annotated[
        Path,
        typer.Argument(help="Path to JSON file containing user data to pre-register"),
    ],
    base_url: BaseUrlOption = "http://localhost:8001",
    admin_email: AdminEmailOption = None,
    admin_password: AdminPasswordOption = None,
):
    """Pre-register users from a JSON file.

    The JSON file should contain a list of user objects with the following fields:
    firstName, lastName, email, and optionally institution, phone, address, city, state, postalCode, country.
    """
    if not users_file.exists():
        _print_error(f"File {users_file} does not exist")
        sys.exit(os.EX_NOINPUT)

    if not admin_email:
        admin_email = typer.prompt("Admin email")

    _print_info(f"Pre-registering users from {users_file} using {base_url}")
    asyncio.run(run_pre_registration(base_url, users_file, admin_email, admin_password))
    _print_success("Pre-registration completed")


@app.command()
def invite(
    guest_email: Annotated[
        str,
        typer.Argument(help="Email address of the guest to invite"),
    ],
    trial_days: Annotated[
        int,
        typer.Option(
            "--trial-days",
            "-t",
            help="Number of days for trial account",
        ),
    ] = None,
    extra_credits: Annotated[
        int,
        typer.Option(
            "--extra-credits",
            "-c",
            help="Extra credits in USD (0-499)",
        ),
    ] = None,
    base_url: BaseUrlOption = "http://localhost:8001",
    admin_email: AdminEmailOption = None,
    admin_password: AdminPasswordOption = None,
):
    """Generate an invitation link for a guest email."""
    if not admin_email:
        admin_email = typer.prompt("Admin email")

    # Validate trial_days and extra_credits
    if trial_days is not None and trial_days <= 0:
        _print_error("Trial days must be a positive integer")
        sys.exit(os.EX_USAGE)

    if extra_credits is not None and (extra_credits < 0 or extra_credits >= 500):
        _print_error("Extra credits must be between 0 and 499")
        sys.exit(os.EX_USAGE)

    _print_info(f"Generating invitation for {guest_email} using {base_url}")
    asyncio.run(
        run_create_invitation(
            base_url,
            guest_email,
            admin_email,
            admin_password,
            trial_days,
            extra_credits,
        )
    )
    _print_success("Invitation generation completed")


@app.command()
def invite_all(
    emails_file: Annotated[
        Path,
        typer.Argument(help="Path to JSON file containing emails to invite"),
    ],
    trial_days: Annotated[
        int,
        typer.Option(
            "--trial-days",
            "-t",
            help="Number of days for trial account",
        ),
    ] = None,
    extra_credits: Annotated[
        int,
        typer.Option(
            "--extra-credits",
            "-c",
            help="Extra credits in USD (0-499)",
        ),
    ] = None,
    base_url: BaseUrlOption = "http://localhost:8001",
    admin_email: AdminEmailOption = None,
    admin_password: AdminPasswordOption = None,
):
    """Generate invitation links for multiple users from a JSON file.

    The JSON file should contain either:
    1. A list of email strings: ["user1@example.com", "user2@example.com"]
    2. A list of objects with an email property: [{"email": "user1@example.com", ...}, ...]
    """
    if not emails_file.exists():
        _print_error(f"File {emails_file} does not exist")
        sys.exit(os.EX_NOINPUT)

    if not admin_email:
        admin_email = typer.prompt("Admin email")

    # Validate trial_days and extra_credits
    if trial_days is not None and trial_days <= 0:
        _print_error("Trial days must be a positive integer")
        sys.exit(os.EX_USAGE)

    if extra_credits is not None and (extra_credits < 0 or extra_credits >= 500):
        _print_error("Extra credits must be between 0 and 499")
        sys.exit(os.EX_USAGE)

    _print_info(f"Generating invitations for users in {emails_file} using {base_url}")
    asyncio.run(
        run_bulk_create_invitation(
            base_url,
            emails_file,
            admin_email,
            admin_password,
            trial_days,
            extra_credits,
        )
    )
    _print_success("Bulk invitation completed")


if __name__ == "__main__":
    app()

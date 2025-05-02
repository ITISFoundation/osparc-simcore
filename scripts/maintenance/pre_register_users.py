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
    $ uv run pre_register_users.py --help

    $ uv run pre_register_users.py pre-register pre_register_users.json --base-url http://localhost:8001 --email admin@email.com

    $ uv run pre_register_users.py invite user@example.com --base-url http://localhost:8001 --email admin@email.com

    $ uv run pre_register_users.py invite-all users.json --base-url http://localhost:8001 --email admin@email.com
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


async def login(
    client: AsyncClient, email: EmailStr, password: SecretStr
) -> dict[str, Any]:
    """Login user with the provided credentials"""
    path = "/v0/auth/login"

    credentials = LoginCredentials(email=email, password=password)

    response = await client.post(
        path,
        json={
            "email": credentials.email,
            "password": credentials.password.get_secret_value(),
        },
    )
    response.raise_for_status()

    return response.json()["data"]


async def logout_current_user(client: AsyncClient):
    path = "/v0/auth/logout"
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
) -> dict[str, Any]:
    """Pre-register a user in the system"""
    path = "/v0/admin/users:pre-register"

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


async def create_invitation(
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


async def pre_register_users_from_file(
    client: AsyncClient,
    users_data: list[PreRegisterUserRequest],
) -> list[dict[str, Any]]:
    """Pre-registers multiple users from a list of user data"""
    results = []
    for user_data in users_data:
        try:
            result = await pre_register_user(
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
            typer.secho(
                f"Successfully pre-registered user: {user_data.email}",
                fg=typer.colors.GREEN,
            )

        except HTTPStatusError as e:
            typer.secho(
                f"Failed to pre-register user {user_data.email} with {e.response.status_code}: {e.response.text}",
                fg=typer.colors.RED,
                err=True,
            )

        except Exception as e:
            typer.secho(
                f"Failed to pre-register user {user_data.email}: {str(e)}",
                fg=typer.colors.RED,
                err=True,
            )

    return results


async def create_invitations_from_list(
    client: AsyncClient,
    emails: list[EmailStr],
    trial_days: PositiveInt | None = None,
    extra_credits: int | None = None,
) -> list[dict[str, Any]]:
    """Generate invitations for multiple users from a list of emails"""
    results = []
    for email in emails:
        try:
            result = await create_invitation(
                client=client,
                guest_email=email,
                trial_days=trial_days,
                extra_credits=extra_credits,
            )
            results.append({"email": email, "invitation": result})
            typer.secho(
                f"Successfully generated invitation for: {email}",
                fg=typer.colors.GREEN,
            )

        except HTTPStatusError as e:
            typer.secho(
                f"Failed to generate invitation for {email} with {e.response.status_code}: {e.response.text}",
                fg=typer.colors.RED,
                err=True,
            )
            results.append({"email": email, "error": str(e)})

        except Exception as e:
            typer.secho(
                f"Failed to generate invitation for {email}: {str(e)}",
                fg=typer.colors.RED,
                err=True,
            )
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

    # Create an HTTP client and process
    async with AsyncClient(base_url=base_url, timeout=30) as client:
        try:
            # Login as admin
            typer.secho(f"Logging in as {admin_email}...", fg=typer.colors.BLUE)
            await login(
                client=client,
                email=admin_email,
                password=admin_password,
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

            # Dump results to a file
            timestamp = datetime.datetime.now(tz=datetime.UTC).strftime("%Y%m%d_%H%M%S")
            input_filename = users_file_path.stem
            output_filename = f"{input_filename}_results_{timestamp}.json"
            output_path = users_file_path.parent / output_filename

            output_path.write_text(json.dumps(results, indent=1))
            typer.secho(
                f"Results written to {output_path}",
                fg=typer.colors.GREEN,
            )

            # Logout
            typer.secho("Logging out...", fg=typer.colors.BLUE)
            await logout_current_user(client)

        except Exception as e:
            typer.secho(f"Error: {str(e)}", fg=typer.colors.RED, err=True)
            sys.exit(os.EX_SOFTWARE)


async def run_generate_invitation(
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
            typer.secho(f"Logging in as {admin_email}...", fg=typer.colors.BLUE)
            await login(
                client=client,
                email=admin_email,
                password=admin_password,
            )

            # Generate invitation
            typer.secho(
                f"Generating invitation for {guest_email}...", fg=typer.colors.BLUE
            )
            result = await create_invitation(
                client, guest_email, trial_days=trial_days, extra_credits=extra_credits
            )

            # Display invitation link
            typer.secho(
                f"Successfully generated invitation for {guest_email}",
                fg=typer.colors.GREEN,
            )
            typer.secho(
                f"Invitation link: {result.get('link', 'No link returned')}",
                fg=typer.colors.GREEN,
            )

            # Save result to a file
            timestamp = datetime.datetime.now(tz=datetime.UTC).strftime("%Y%m%d_%H%M%S")
            output_filename = f"invitation_{guest_email.split('@')[0]}_{timestamp}.json"
            output_path = Path(output_filename)
            output_path.write_text(json.dumps(result, indent=1))
            typer.secho(
                f"Result written to {output_path}",
                fg=typer.colors.GREEN,
            )

            # Logout
            typer.secho("Logging out...", fg=typer.colors.BLUE)
            await logout_current_user(client)

        except HTTPStatusError as e:
            typer.secho(
                f"Failed to generate invitation with {e.response.status_code}: {e.response.text}",
                fg=typer.colors.RED,
                err=True,
            )
            sys.exit(os.EX_SOFTWARE)
        except Exception as e:
            typer.secho(f"Error: {str(e)}", fg=typer.colors.RED, err=True)
            sys.exit(os.EX_SOFTWARE)


async def run_bulk_invitation(
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
                typer.secho(
                    "Error: File must contain either a list of email strings or objects with 'email' property",
                    fg=typer.colors.RED,
                    err=True,
                )
                sys.exit(os.EX_DATAERR)

            emails = TypeAdapter(
                list[Annotated[BeforeValidator(lambda s: s.lower()), EmailStr]]
            ).validate_python(data)
        else:
            typer.secho(
                "Error: File must contain a JSON array",
                fg=typer.colors.RED,
                err=True,
            )
            sys.exit(os.EX_DATAERR)

    except json.JSONDecodeError:
        typer.secho(
            f"Error: {emails_file_path} is not a valid JSON file",
            fg=typer.colors.RED,
            err=True,
        )
        sys.exit(os.EX_DATAERR)
    except ValidationError as e:
        typer.secho(
            f"Error: Invalid email format: {e}",
            fg=typer.colors.RED,
            err=True,
        )
        sys.exit(os.EX_DATAERR)
    except Exception as e:
        typer.secho(
            f"Error reading or parsing {emails_file_path}: {str(e)}",
            fg=typer.colors.RED,
            err=True,
        )
        sys.exit(os.EX_IOERR)

    # Create an HTTP client and process
    async with AsyncClient(base_url=base_url, timeout=30) as client:
        try:
            # Login as admin
            typer.secho(f"Logging in as {admin_email}...", fg=typer.colors.BLUE)
            await login(
                client=client,
                email=admin_email,
                password=admin_password,
            )

            # Generate invitations
            typer.secho(
                f"Generating invitations for {len(emails)} users...",
                fg=typer.colors.BLUE,
            )
            results = await create_invitations_from_list(
                client, emails, trial_days=trial_days, extra_credits=extra_credits
            )

            successful = sum(1 for r in results if "invitation" in r)
            typer.secho(
                f"Successfully generated {successful} invitations out of {len(emails)} users",
                fg=typer.colors.GREEN,
            )

            # Dump results to a file
            timestamp = datetime.datetime.now(tz=datetime.UTC).strftime("%Y%m%d_%H%M%S")
            input_filename = emails_file_path.stem
            output_filename = f"{input_filename}_invitations_{timestamp}.json"
            output_path = emails_file_path.parent / output_filename

            output_path.write_text(json.dumps(results, indent=1))
            typer.secho(
                f"Results written to {output_path}",
                fg=typer.colors.GREEN,
            )

            # Logout
            typer.secho("Logging out...", fg=typer.colors.BLUE)
            await logout_current_user(client)

        except Exception as e:
            typer.secho(f"Error: {str(e)}", fg=typer.colors.RED, err=True)
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
        typer.secho(
            "Error: Trial days must be a positive integer",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=os.EX_USAGE)

    if extra_credits is not None and (extra_credits < 0 or extra_credits >= 500):
        typer.secho(
            "Error: Extra credits must be between 0 and 499",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=os.EX_USAGE)

    typer.secho(
        f"Generating invitation for {guest_email} using {base_url}",
        fg=typer.colors.BLUE,
    )
    asyncio.run(
        run_generate_invitation(
            base_url,
            guest_email,
            admin_email,
            admin_password,
            trial_days,
            extra_credits,
        )
    )
    typer.secho("Invitation generation completed", fg=typer.colors.GREEN)


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
        typer.secho(
            f"Error: File {emails_file} does not exist", fg=typer.colors.RED, err=True
        )
        raise typer.Exit(code=os.EX_NOINPUT)

    if not admin_email:
        admin_email = typer.prompt("Admin email")

    # Validate trial_days and extra_credits
    if trial_days is not None and trial_days <= 0:
        typer.secho(
            "Error: Trial days must be a positive integer",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=os.EX_USAGE)

    if extra_credits is not None and (extra_credits < 0 or extra_credits >= 500):
        typer.secho(
            "Error: Extra credits must be between 0 and 499",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=os.EX_USAGE)

    typer.secho(
        f"Generating invitations for users in {emails_file} using {base_url}",
        fg=typer.colors.BLUE,
    )
    asyncio.run(
        run_bulk_invitation(
            base_url,
            emails_file,
            admin_email,
            admin_password,
            trial_days,
            extra_credits,
        )
    )
    typer.secho("Bulk invitation completed", fg=typer.colors.GREEN)


if __name__ == "__main__":
    app()

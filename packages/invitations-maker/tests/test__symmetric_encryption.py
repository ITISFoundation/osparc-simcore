import base64
import json
import os
from urllib.parse import parse_qs, urlparse

from cryptography.fernet import Fernet, InvalidToken
from pytest import MonkeyPatch
from yarl import URL


def produce(guest_email: str):
    secret_key = os.environ["SECRET_KEY"].strip().encode()
    fernet = Fernet(secret_key)

    data = {"guest": guest_email, "check": 123, "version": 1}

    message: bytes = json.dumps(data).encode()  # bytpes
    encrypted = fernet.encrypt(message)

    # WARNING: how to encode the encrypted message
    p = (
        URL()
        .with_path("registration")
        .with_query(invitation=base64.urlsafe_b64encode(encrypted).decode())
    )
    url = f"http://127.0.0.1.nip.io:9081/#{p}"
    return url


def consume(url):
    frontend_entrypoint = urlparse(urlparse(f"{url}").fragment)
    query_params = parse_qs(frontend_entrypoint.query)
    invitation = query_params["invitation"][0]

    invitation_code = base64.urlsafe_b64decode(invitation)

    try:
        secret_key = os.environ["SECRET_KEY"].strip().encode()
        fernet = Fernet(secret_key)
        decripted = fernet.decrypt(invitation_code)

        data = json.loads(decripted.decode())
        return data

    except json.decoder.JSONDecodeError as err:
        print("Invalid data", err)
        raise

    except InvalidToken as err:
        # TODO: cannot decode
        print("Invalid Key", err)
        raise


def test_it(monkeypatch: MonkeyPatch):
    secret_key = Fernet.generate_key()
    monkeypatch.setenv("SECRET_KEY", secret_key.decode())

    # invitation generator app
    invitation_url = produce(guest_email="guest@gmail.com")

    # osparc side
    invitation_data = consume(invitation_url)
    print(json.dumps(invitation_data, indent=1))

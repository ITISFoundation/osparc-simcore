# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

import base64
import json
import os
from urllib.parse import parse_qsl, urlparse

import pytest
from cryptography.fernet import Fernet, InvalidToken
from faker import Faker
from starlette.datastructures import URL


def produce(guest_email: str):
    secret_key = os.environ["SECRET_KEY"].strip().encode()
    fernet = Fernet(secret_key)

    data = {"guest": guest_email, "check": 123, "version": 1}

    message: bytes = json.dumps(data).encode()  # bytpes
    encrypted = fernet.encrypt(message)

    # WARNING: how to encode the encrypted message
    p = URL("/registration").include_query_params(
        invitation=base64.urlsafe_b64encode(encrypted).decode()
    )
    url = URL(scheme="http", hostname="127.0.0.1", port=8000, fragment=f"{p}")
    return url


def consume(url):
    frontend_entrypoint = urlparse(urlparse(f"{url}").fragment)
    query_params = dict(parse_qsl(frontend_entrypoint.query))
    invitation: str = query_params["invitation"]
    invitation_code: bytes = base64.urlsafe_b64decode(invitation)

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
        print("Invalid Key", err)
        raise


@pytest.fixture(
    params=[
        "en_US",  # English (United States)
        "fr_FR",  # French (France)
        "de_DE",  # German (Germany)
        "ru_RU",  # Russian
        "ja_JP",  # Japanese
        "zh_CN",  # Chinese (Simplified)
        "ko_KR",  # Korean
        "ar_EG",  # Arabic (Egypt)
        "he_IL",  # Hebrew (Israel)
        "hi_IN",  # Hindi (India)
        "th_TH",  # Thai (Thailand)
        "vi_VN",  # Vietnamese (Vietnam)
        "ta_IN",  # Tamil (India)
    ]
)
def fake_email(request):
    locale = request.param
    faker = Faker(locale)
    # Use a localized name for the username part of the email
    name = faker.name().replace(" ", "").replace(".", "").lower()
    # Construct the email address
    return f"{name}@example.{locale.split('_')[-1].lower()}"


def test_encrypt_and_decrypt(monkeypatch: pytest.MonkeyPatch, fake_email: str):
    secret_key = Fernet.generate_key()
    monkeypatch.setenv("SECRET_KEY", secret_key.decode())

    # invitation generator app
    invitation_url = produce(guest_email=fake_email)
    assert invitation_url.fragment

    # osparc side
    invitation_data = consume(invitation_url)
    print(json.dumps(invitation_data, indent=1))
    assert invitation_data["guest"] == fake_email

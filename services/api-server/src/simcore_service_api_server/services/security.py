import subprocess  # nosec
from subprocess import CalledProcessError, CompletedProcess  # nosec

from passlib.context import CryptContext

__pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return __pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return __pwd_context.hash(password)


def create_secret_key() -> str:
    # NOTICE that this key is reset when server is restarted!
    try:
        proc: CompletedProcess = subprocess.run(  # nosec
            "openssl rand -hex 32", check=True, shell=True
        )
    except (CalledProcessError, FileNotFoundError) as why:
        raise ValueError("Cannot create secret key") from why
    return str(proc.stdout).strip()

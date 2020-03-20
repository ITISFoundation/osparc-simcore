import json
import subprocess  # nosec
from datetime import datetime
from subprocess import CalledProcessError, CompletedProcess  # nosec
from typing import Dict


def to_bool(s: str) -> bool:
    return s.lower() in ["true", "1", "yes"]


def jsoncoverter(obj):
    if isinstance(obj, datetime):
        return obj.__str__()
    if isinstance(obj, bytes):
        return str(obj)
    return obj


def json_dumps(obj: Dict) -> str:
    return json.dumps(obj, indent=2, default=jsoncoverter)


def create_secret_key() -> str:
    # NOTICE that this key is reset when server is restarted!

    try:
        proc: CompletedProcess = subprocess.run(  # nosec
            "openssl rand -hex 32", check=True, shell=True
        )
    except (CalledProcessError, FileNotFoundError) as why:
        raise ValueError(f"Cannot create secret key") from why
    return str(proc.stdout).strip()

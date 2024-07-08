import json

from pydantic_settings import BaseSettings


def dump_dotenv(settings: BaseSettings):
    result = [
        f"{key}={val}" for key, val in json.loads(settings.model_dump_json()).items()
    ]
    print("\n".join(result))

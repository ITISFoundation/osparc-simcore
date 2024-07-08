from locust_settings import LocustSettings, dump_dotenv
from workflow import UserSettings


class MetaModelingSettings(UserSettings, LocustSettings):
    pass


if __name__ == "__main__":
    dump_dotenv(MetaModelingSettings())

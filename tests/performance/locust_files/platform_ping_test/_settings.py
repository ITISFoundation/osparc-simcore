from locust_settings import LocustSettings, dump_dotenv
from platform_ping_test import LocustAuth


class LoadTestSettings(LocustAuth, LocustSettings):
    pass


if __name__ == "__main__":
    dump_dotenv(LoadTestSettings())

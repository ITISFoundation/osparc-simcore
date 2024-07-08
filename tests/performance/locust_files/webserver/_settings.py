from locust_settings import LocustSettings, dump_dotenv
from locustfile import TemplateSettings


class LoadTestSettings(TemplateSettings, LocustSettings):
    pass


if __name__ == "__main__":
    dump_dotenv(LoadTestSettings())

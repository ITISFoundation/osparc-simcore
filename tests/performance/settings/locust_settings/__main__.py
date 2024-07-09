from ._dump_dotenv import dump_dotenv
from ._locust_settings import LocustSettings

if __name__ == "__main__":
    dump_dotenv(LocustSettings())

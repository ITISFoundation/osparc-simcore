from pathlib import Path

from faker import Faker
from servicelib.r_clone_utils import config_file


async def test_config_file(faker: Faker) -> None:
    text_to_write = faker.text()
    async with config_file(text_to_write) as file_name:
        assert text_to_write == Path(file_name).read_text()
    assert Path(file_name).exists() is False

import pytest
from servicelib.secure_random import secure_randint


@pytest.mark.parametrize("start, end", [(1, 10)])
async def test_secure_randint(start: int, end: int):
    for _ in range(1000):
        random_number = secure_randint(start, end)
        assert start <= random_number <= end

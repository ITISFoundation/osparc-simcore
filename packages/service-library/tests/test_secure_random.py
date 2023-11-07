from servicelib.secure_random import secure_randint


async def test_secure_randint():
    for _ in range(1000):
        start = 1
        end = 10
        random_number = secure_randint(start, end)
        assert start <= random_number <= end

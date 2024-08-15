import random


def test_it():
    with open(f"/tmp/test_{random.random()}_file.txt", "wb") as f:
        f.write(b"\0" * 1024 * 1024)

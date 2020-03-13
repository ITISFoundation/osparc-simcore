import logging

import pytest

# Selection of core and tool services started in this swarm fixture (integration)
core_services = ["storage", "postgres", "rabbit"]

ops_services = [
    "minio",
    #    'adminer'
]


async def test_sleepers(loop):
    pass

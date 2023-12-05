from aws_library.ec2.utils import compose_user_data
from faker import Faker


def test_compose_user_data(faker: Faker):
    assert compose_user_data(faker.pystr()).startswith("#!/bin/bash\n")
    assert compose_user_data(faker.pystr()).endswith("\n")

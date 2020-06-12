# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
import pytest
from pydantic import BaseModel


def create_fake(model: BaseModel):
    from faker import Faker

    fake = Faker()

    # for field in model.__fie
    # navigate fields
    # if example cls.Config.schema_extra.get("example")
    # type
    # default or some value in fake

from pprint import pprint
from typing import List

import attr
from pydantic import BaseModel, ValidationError, constr
from sqlalchemy import Column, Integer, String
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.ext.declarative import declarative_base

# https://pydantic-docs.helpmanual.io/usage/models/#orm-mode-aka-arbitrary-class-instances

Base = declarative_base()


class CompanyOrm(Base):
    __tablename__ = "companies"
    id = Column(Integer, primary_key=True, nullable=False)
    public_key = Column(String(20), index=True, nullable=False, unique=True)
    name = Column(String(63), unique=True)
    domains = Column(ARRAY(String(255)))


class Bar(BaseModel):
    apple = "x"
    banana = "y"


class CompanyModel(BaseModel):
    id: int
    public_key: constr(max_length=20)
    name: constr(max_length=63)
    # NO DOMAINS!
    other_value: int = 33

    foo: Bar = Bar()

    class Config:
        orm_mode = True


@attr.s(auto_attribs=True)
class Company:
    id: int
    name: str
    public_key: str = 55


if __name__ == "__main__":

    co_orm = CompanyOrm(
        id=123,
        public_key="foobar",
        name="Testing",
        domains=["example.com", "foobar.com"],
    )
    pprint(co_orm)

    print("-" * 30)

    co_model = CompanyModel.from_orm(co_orm)

    print(co_model.__fields_set__)
    assert "other_value" not in co_model.__fields_set__
    assert "foo" not in co_model.__fields_set__

    print("-" * 30)
    assert "other_value" in co_model.__fields__

    pprint(co_model)
    pprint(co_model.dict())
    # co_model.json()

    print("-" * 30)
    pprint(co_model.schema())
    # co_model.schema_json() ->

    print("-" * 30)
    print(co_model.__config__)

    # CAN convert from attr type! ORM is everything with attributes?
    obj = Company(22, "pedro", "foo")

    import pdb

    pdb.set_trace()
    co_model.from_orm(obj)

    try:
        co_model.parse_obj(obj)
    except ValidationError as ee:
        print("obj has to be a dict!")

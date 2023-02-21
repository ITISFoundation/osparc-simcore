import sqlalchemy as sa
from sqlalchemy import Column, Integer, String

from .base import Base


class DAG(Base):
    """Table with Directed Acyclic Graphs

    Managed  by the catalog's service
    """

    __tablename__ = "dags"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, index=True)
    version = Column(String)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    contact = Column(String, index=True)
    workbench = Column(sa.JSON, nullable=False)


dags = DAG.__table__

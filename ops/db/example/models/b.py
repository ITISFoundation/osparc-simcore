from sqlalchemy import Column, Integer, String
from base import Base

class B(Base):

    __tablename__ = 'B'

    id = Column(Integer, primary_key=True)
    name = Column(String)

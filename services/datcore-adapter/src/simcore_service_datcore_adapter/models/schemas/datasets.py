from pydantic import BaseModel


class DatasetMetaData(BaseModel):
    id: str
    display_name: str

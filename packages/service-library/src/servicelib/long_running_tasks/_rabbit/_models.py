from pydantic import BaseModel


class RPCErrorResponse(BaseModel):
    str_traceback: str
    error_object: str

from fastapi import FastAPI, Depends, Security, HTTPException

import uvicorn

from fastapi.security.api_key import APIKeyHeader
from starlette.status import HTTP_403_FORBIDDEN

API_KEY = "1234567asdfgh"
API_KEY_NAME = "access_token" # this is acces


def get_active_user(
    api_key: str = Security(APIKeyHeader(name=API_KEY_NAME, scheme_name="ApiKeyAuth"))
) -> str:
    # the api_key is a jwt created upon login
    #
    # - decode jwt
    # - authenticate user

    if api_key != API_KEY:
        raise HTTPException(
            status_code=HTTP_403_FORBIDDEN, detail="Invalid credentials"
        )


    return user_id


app = FastAPI()


@app.get("/foo")
def foo(user_id: str = Depends(get_active_user)):
    return f"hi {user_id}"


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

from fastapi import Depends, FastAPI
from fastapi.requests import Request
from fastapi.applications import State
import uvicorn

app = FastAPI(title="get_app_state")

# Dependences WITH arguents
def _get_app(request: Request) -> FastAPI:
    return request.app


def _get_app_state(request: Request) -> State:
    return request.app.state


@app.get("/app")
async def get_server_ip(my_app: FastAPI = Depends(_get_app)):
    assert my_app == app
    return my_app.title


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

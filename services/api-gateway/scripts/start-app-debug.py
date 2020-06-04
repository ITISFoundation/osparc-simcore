import uvicorn
from simcore_service_api_gateway.main import the_app

if __name__ == "__main__":
    uvicorn.run(the_app, port=8001, host="0.0.0.0")

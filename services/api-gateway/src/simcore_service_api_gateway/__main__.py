""" Main application entry point

 `python -m simcore_service_api_gateway ...`

Why does this file exist, and why __main__? For more info, read:

- https://www.python.org/dev/peps/pep-0338/
- https://docs.python.org/3/using/cmdline.html#cmdoption-m
"""
import uvicorn

from simcore_service_api_gateway.main import the_app
from simcore_service_api_gateway.config import uvicorn_settings

def main():
    uvicorn.run(the_app, **uvicorn_settings)

if __name__ == "__main__":
    main()

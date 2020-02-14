""" Main application entry point

 `python -m simcore_service_catalog ...`

Why does this file exist, and why __main__? For more info, read:

- https://www.python.org/dev/peps/pep-0338/
- https://docs.python.org/3/using/cmdline.html#cmdoption-m
"""
import uvicorn

from .main import app
from .config import uvicorn_settings

def main():
    uvicorn.run(app, **uvicorn_settings)

if __name__ == "__main__":
    main()

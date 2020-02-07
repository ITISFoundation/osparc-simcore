""" Main application entry point

 `python -m simcore_service_catalog ...`

Why does this file exist, and why __main__? For more info, read:

- https://www.python.org/dev/peps/pep-0338/
- https://docs.python.org/3/using/cmdline.html#cmdoption-m
"""
import uvicorn

from .main import app
from .config import app_config

if __name__ == "__main__":
    uvicorn.run(app, **app_config)

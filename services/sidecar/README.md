# Sidecar

Use sidecar container to control computational service.

TODO: See issue #198

```bash

# create an prepare a clean virtual environment ...
python3 -m venv .venv
source .venv/bin/activate
pip3 install --upgrade pip setuptools wheel
# ..or
make .venv
source .venv/bin/activate


cd services/sidecar

# for development (edit mode)
# see how this packages is listed with a path to it src/ folder
pip3 install -r requirements/dev.txt
pip3 list


# for production
pip3 install -r requirements/prod.txt
pip3 list
```

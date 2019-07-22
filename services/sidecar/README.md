# sidecar

[![Docker Pulls](https://img.shields.io/docker/pulls/itisfoundation/sidecar.svg)](https://hub.docker.com/r/itisfoundation/sidecar/tags)
[![](https://images.microbadger.com/badges/image/itisfoundation/sidecar.svg)](https://microbadger.com/images/itisfoundation/sidecar "More on service image in registry")
[![](https://images.microbadger.com/badges/version/itisfoundation/sidecar.svg)](https://microbadger.com/images/itisfoundation/sidecar "More on service image in registry")
[![](https://images.microbadger.com/badges/commit/itisfoundation/sidecar.svg)](https://microbadger.com/images/itisfoundation/sidecar "More on service image in registry")


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

# apihub

[![Docker Pulls](https://img.shields.io/docker/pulls/itisfoundation/apihub.svg)](https://hub.docker.com/r/itisfoundation/apihub/tags)
<!-- TODO: activate hook for microbadger
[![](https://images.microbadger.com/badges/image/itisfoundation/apihub.svg)](https://microbadger.com/images/itisfoundation/apihub "More on service image in registry")
[![](https://images.microbadger.com/badges/version/itisfoundation/apihub.svg)](https://microbadger.com/images/itisfoundation/apihub "More on service image in registry")
[![](https://images.microbadger.com/badges/commit/itisfoundation/apihub.svg)](https://microbadger.com/images/itisfoundation/apihub "More on service image in registry")
-->

The apihub purpose is to serve api specifications to other parts of the oSparc platform.
The file are served by default on port 8043.

## Usage

```bash

  # development image
  docker build --target development -t apihub:dev .
  docker run -v %APIS_FILES%:/srv/http/apis -p 8043:8043 apihub:dev

  # production image
  docker build --target production -t apihub:prod .
  docker run -p 8043:8043 apihub:prod

```

It is also a part of the oSparc platform and is started together with the platform.
Note: If a service/package rely on the availability of the APIs then the apihub must be started first.

# osparc-simcore platform

[![Waffle.io - Columns and their card count](https://badge.waffle.io/ITISFoundation/osparc-simcore.svg?columns=Backlog,In%20Progress,Review,Done)](https://waffle.io/ITISFoundation/osparc-simcore)
[![Build Status](https://travis-ci.org/ITISFoundation/osparc-simcore.svg?branch=master)](https://travis-ci.org/ITISFoundation/osparc-simcore)
[![Requirements Status](https://requires.io/github/ITISFoundation/osparc-simcore/requirements.svg?branch=master)](https://requires.io/github/ITISFoundation/osparc-simcore/requirements/?branch=master)
[![Coverage Status](https://coveralls.io/repos/github/ITISFoundation/osparc-simcore/badge.svg?branch=master)](https://coveralls.io/github/ITISFoundation/osparc-simcore?branch=master)


[![](https://img.shields.io/microbadger/image-size/itisfoundation/webserver/staging-latest.svg?label=webserver&style=flat)](https://microbadger.com/images/itisfoundation/webserver "More on itisfoundation/webserver:staging-latest image")
[![](https://img.shields.io/microbadger/image-size/itisfoundation/director/staging-latest.svg?label=director&style=flat)](https://microbadger.com/images/itisfoundation/director "More on itisfoundation/director:staging-latest image")
[![](https://img.shields.io/microbadger/image-size/itisfoundation/sidecar/staging-latest.svg?label=sidecar&style=flat)](https://microbadger.com/images/itisfoundation/sidecar "More on itisfoundation/sidecar:staging-latest image")
[![](https://img.shields.io/microbadger/image-size/itisfoundation/storage/staging-latest.svg?label=storage&style=flat)](https://microbadger.com/images/itisfoundation/director "More on itisfoundation/director:staging-latest image")

## Overview

![service-web](docs/img/service-interaction.svg)


```bash
  # clone repo
  git clone https://github.com/ITISFoundation/osparc-simcore.git
  cd osparc-simcore

  # build core services
  make build

  # starts swarm and deploys services
  make up

  # open browser in:
  #  localhost:9081 - simcore front-end site
  #
  xdg-open http://localhost:9081/

  # stops
  make down
```




**WARNING** This application is still under development and still not suitable for production purposes.

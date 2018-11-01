# osparc-simcore platform

[![Build Status](https://travis-ci.org/ITISFoundation/osparc-simcore.svg?branch=master)](https://travis-ci.org/ITISFoundation/osparc-simcore)
[![Waffle.io - Columns and their card count](https://badge.waffle.io/ITISFoundation/osparc-simcore.svg?columns=all)](https://waffle.io/ITISFoundation/osparc-simcore)

## Overview

![service-web](docs/img/service-interaction.svg)


```bash
  git clone git@github.com:ITISFoundation/osparc-simcore.git

  # Set environment variable by copying & editing `.env` file
  cd osparc-simcore
  cp .env-devel .env

  # builds
  make build

  # starts
  make up

  # open browser in:
  #  localhost:9081 - simcore front-end site
  #
  xdg-open http://localhost:9081/

  # stops
  make down
```


## Development

- To run linters in host machine

```bash
  make pylint
```

**WARNING** This application is still under development and still not suitable for production purposes.

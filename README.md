# osparc-simcore platform

[![Waffle.io - Columns and their card count](https://badge.waffle.io/ITISFoundation/osparc-simcore.svg?columns=Backlog,In%20Progress,Review,Done)](https://waffle.io/ITISFoundation/osparc-simcore)
[![Build Status](https://travis-ci.org/ITISFoundation/osparc-simcore.svg?branch=master)](https://travis-ci.org/ITISFoundation/osparc-simcore)
[![Requirements Status](https://requires.io/github/ITISFoundation/osparc-simcore/requirements.svg?branch=master)](https://requires.io/github/ITISFoundation/osparc-simcore/requirements/?branch=master)


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



**WARNING** This application is still under development and still not suitable for production purposes.

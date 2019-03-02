# osparc-simcore platform

<!-- NOTE: when branched replace `master` in urls -->
[`master`](https://github.com/itisfoundation/osparc-simcore/tree/master)
[![Requires.io]](https://requires.io/github/ITISFoundation/osparc-simcore/requirements/?branch=master "State of third party python dependencies")
[![travis-ci]](https://travis-ci.org/ITISFoundation/osparc-simcore "State of CI: build, test and pushing images")
[![coverals.io]](https://coveralls.io/github/ITISFoundation/osparc-simcore?branch=master "Test coverage")
[![doc.pages]](https://itisfoundation.github.io/)

[![waffle.io]](https://waffle.io/ITISFoundation/osparc-simcore "Scrum wall")

[![webserver]](https://microbadger.com/images/itisfoundation/webserver "More on itisfoundation/webserver:staging-latest image")
[![director]](https://microbadger.com/images/itisfoundation/director "More on itisfoundation/director:staging-latest image")
[![sidecar]](https://microbadger.com/images/itisfoundation/sidecar "More on itisfoundation/sidecar:staging-latest image")
[![storage]](https://microbadger.com/images/itisfoundation/storage "More on itisfoundation/storage:staging-latest image")

<!-- ADD HERE ALL BADGE URLS -->
[waffle.io]:https://badge.waffle.io/ITISFoundation/osparc-simcore.svg?columns=Backlog,In%20Progress,Review,Done
[Requires.io]:https://img.shields.io/requires/github/ITISFoundation/osparc-simcore.svg
[travis-ci]:https://travis-ci.org/ITISFoundation/osparc-simcore.svg?branch=master
[coverals.io]:https://coveralls.io/repos/github/ITISFoundation/osparc-simcore/badge.svg?branch=master
[doc.pages]:https://img.shields.io/website-up-down-green-red/https/itisfoundation.github.io.svg?label=documentation
[webserver]:https://img.shields.io/microbadger/image-size/itisfoundation/webserver/staging-latest.svg?label=webserver&style=flat
[director]:https://img.shields.io/microbadger/image-size/itisfoundation/director/staging-latest.svg?label=director&style=flat
[sidecar]:https://img.shields.io/microbadger/image-size/itisfoundation/sidecar/staging-latest.svg?label=sidecar&style=flat
[storage]:https://img.shields.io/microbadger/image-size/itisfoundation/sidecar/staging-latest.svg?label=sidecar&style=flat
<!---------------------------->

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

# osparc-simcore platform

<!-- NOTE: when branched replace `master` in urls -->
[`master`](https://github.com/itisfoundation/osparc-simcore/tree/master)
[![Requires.io]](https://requires.io/github/ITISFoundation/osparc-simcore/requirements/?branch=master "State of third party python dependencies")
[![travis-ci]](https://travis-ci.org/ITISFoundation/osparc-simcore "State of CI: build, test and pushing images")
[![coverals.io]](https://coveralls.io/github/ITISFoundation/osparc-simcore?branch=master "Test coverage")
[![github.io]](https://itisfoundation.github.io/)


[![itis.dockerhub]](https://hub.docker.com/u/itisfoundation)
[![webserver]](https://microbadger.com/images/itisfoundation/webserver "More on itisfoundation/webserver:staging-latest image")
[![director]](https://microbadger.com/images/itisfoundation/director "More on itisfoundation/director:staging-latest image")
[![sidecar]](https://microbadger.com/images/itisfoundation/sidecar "More on itisfoundation/sidecar:staging-latest image")
[![storage]](https://microbadger.com/images/itisfoundation/storage "More on itisfoundation/storage:staging-latest image")

<!-- ADD HERE ALL BADGE URLS -->
[Requires.io]:https://img.shields.io/requires/github/ITISFoundation/osparc-simcore.svg
[travis-ci]:https://travis-ci.org/ITISFoundation/osparc-simcore.svg?branch=master
[coverals.io]:https://coveralls.io/repos/github/ITISFoundation/osparc-simcore/badge.svg?branch=master
[github.io]:https://img.shields.io/website-up-down-green-red/https/itisfoundation.github.io.svg?label=documentation
[itis.dockerhub]:https://img.shields.io/website/https/hub.docker.com/u/itisfoundation.svg?down_color=red&label=dockerhub%20repos&up_color=green
[webserver]:https://img.shields.io/microbadger/image-size/itisfoundation/webserver/staging-latest.svg?label=webserver&style=flat
[director]:https://img.shields.io/microbadger/image-size/itisfoundation/director/staging-latest.svg?label=director&style=flat
[sidecar]:https://img.shields.io/microbadger/image-size/itisfoundation/sidecar/staging-latest.svg?label=sidecar&style=flat
[storage]:https://img.shields.io/microbadger/image-size/itisfoundation/storage/staging-latest.svg?label=storage&style=flat
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

**WARNING** This application is **still under development** and still not suitable for Staging purposes.


## Release workflow

```mermaid
sequenceDiagram
participant Feature
participant Master
participant Hotfix
participant Staging

Master->>Feature: create feature1 branch
Note over Feature: develop feature1...
Feature-->>Master: Pull Request feature1
Master->Master: autodeploys to master.dev

Master->>Feature: create feature2 branch
Note over Feature: develop feature2...
Feature-->>Master: Pull Request feature2
Master->Master: autodeploys to master.dev

Master-->>Staging: Pull Request staging1
Staging->Staging: autodeploys to staging.io
Note over Staging: testing...

Master->>Feature: create feature3 branch
Note over Feature: develop feature3...
Feature-->>Master: Pull Request feature3
Master->Master: autodeploys to master.dev

Master->>Feature: create feature4 branch
Note over Feature: develop feature4...
Feature-->>Master: Pull Request feature4
Master->Master: autodeploys to master.dev

Master-->>Staging: Pull Request staging2
Staging->Staging: autodeploys to staging.io
Note over Staging: testing...
Staging->Staging: RELEASE: Tag v1.0.0 - autodeploys to osparc.io

Staging->>Hotfix: create hotfix1 branch
Note over Hotfix: fix issue...
Hotfix-->>Staging: Pull request hotfix1
Note over Staging: testing...
Staging->Staging: RELEASE: Tag v1.0.1 - autodeploys to osparc.io
Hotfix-->>Master: Pull request hotfix1
Master->Master: autodeploys to master.dev

Master->>Feature: create feature5 branch
Note over Feature: develop feature5...
Feature-->>Master: Pull Request feature5
Master->Master: autodeploys to master.dev

Master->>Feature: create feature6 branch
Note over Feature: develop feature6...
Feature-->>Master: Pull Request feature6
Master->Master: autodeploys to master.dev
```

# osparc-simcore platform

**WARNING** This application is **still under development**.

<!-- NOTE: when branched replace `master` in urls -->
[`master`](https://github.com/itisfoundation/osparc-simcore/tree/master)
[![Code style: black]](https://github.com/psf/black)
[![Requires.io]](https://requires.io/github/ITISFoundation/osparc-simcore/requirements/?branch=master "State of third party python dependencies")
[![travis-ci]](https://travis-ci.org/ITISFoundation/osparc-simcore "State of CI: build, test and pushing images")
![Github-CI Push/PR](https://github.com/ITISFoundation/osparc-simcore/workflows/Github-CI%20Push/PR/badge.svg)
[![coveralls.io]](https://coveralls.io/github/ITISFoundation/osparc-simcore?branch=master)
[![codecov.io]](https://codecov.io/gh/ITISFoundation/osparc-simcore)
[![github.io]](https://itisfoundation.github.io/)
[![itis.dockerhub]](https://hub.docker.com/u/itisfoundation)



<!-- ADD HERE ALL BADGE URLS -->
[Code style: black]:https://img.shields.io/badge/code%20style-black-000000.svg
[Requires.io]:https://img.shields.io/requires/github/ITISFoundation/osparc-simcore.svg
[travis-ci]:https://travis-ci.org/ITISFoundation/osparc-simcore.svg?branch=master
[github.io]:https://img.shields.io/website-up-down-green-red/https/itisfoundation.github.io.svg?label=documentation
[itis.dockerhub]:https://img.shields.io/website/https/hub.docker.com/u/itisfoundation.svg?down_color=red&label=dockerhub%20repos&up_color=green
[coveralls.io]:https://coveralls.io/repos/github/ITISFoundation/osparc-simcore/badge.svg?branch=master
[codecov.io]:https://codecov.io/gh/ITISFoundation/osparc-simcore/branch/master/graph/badge.svg

<!---------------------------->

## Overview

simcore-stack when deployed locally:

![](docs/img/.stack-simcore-version.yml.png)

## Usage

```bash
  # clone repo
  git clone https://github.com/ITISFoundation/osparc-simcore.git
  cd osparc-simcore

  # show setup info and build core services
  make info build

  # starts swarm and deploys services
  make up-prod

  # display swarm configuration
  make info-swarm

  # open browser in:
  #  localhost:9081 - simcore front-end site
  #
  xdg-open http://localhost:9081/

  # stops
  make down
```

## Requirements

To build and run:

- docker
- make >=4.2
- awk, jq (optional tools within makefiles)
- swagger-cli (make sure to have a recent version of nodejs)

To develop, in addition:

- python 3.6 (this dependency will be deprecated soon)
- nodejs for client part (this dependency will be deprecated soon)
- [vscode] (highly recommended)

This project works and is developed mainly under **linux** but, with some adjustments, it can also be done under windows (see notes below).

##### Setup for **windows**

In windows, it works under [WSL] (windows subsystem for linux). Some details on the setup:

- [Install](https://chocolatey.org/docs/installation) [chocolatey] package manager
  - ``choco install docker-for-windows``
  - ``choco install wsl`` or using [instructions](https://docs.microsoft.com/en-us/windows/wsl/install-win10)
-  Follow **all details** on [how to setup flawlessly](https://nickjanetakis.com/blog/setting-up-docker-for-windows-and-wsl-to-work-flawlessly) docker for windows and [WSL]


## Releases

- [Git release workflow](ops/README.md)
- Public [releases](https://github.com/ITISFoundation/osparc-simcore/releases)
- Production in https://osparc.io
- [Staging instructions](docs/staging-instructions.md)




<!-- ADD REFERENCES BELOW AND KEEP THEM IN ALPHABETICAL ORDER -->
[chocolatey]:https://chocolatey.org/
[vscode]:https://code.visualstudio.com/
[WSL]:https://docs.microsoft.com/en-us/windows/wsl/faq

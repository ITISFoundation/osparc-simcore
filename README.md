# osparc-simcore platform

<p align="center">
<img src="https://user-images.githubusercontent.com/32800795/61083844-ff48fb00-a42c-11e9-8e63-fa2d709c8baf.png" width="500">
</p>


<!-- NOTE: when branched replace `master` in urls -->
[![Code style: black]](https://github.com/psf/black)
[![Requires.io]](https://requires.io/github/ITISFoundation/osparc-simcore/requirements/?branch=master "State of third party python dependencies")
[![travis-ci]](https://travis-ci.org/ITISFoundation/osparc-simcore "State of CI: build, test and pushing images")
[![Github-CI Push/PR]](https://github.com/ITISFoundation/osparc-simcore/actions?query=workflow%3A%22Github-CI+Push%2FPR%22+branch%3Amaster)
[![coveralls.io]](https://coveralls.io/github/ITISFoundation/osparc-simcore?branch=master)
[![codecov.io]](https://codecov.io/gh/ITISFoundation/osparc-simcore)
[![github.io]](https://itisfoundation.github.io/)
[![itis.dockerhub]](https://hub.docker.com/u/itisfoundation)
[![license]](./LICENSE)


<!-- ADD HERE ALL BADGE URLS. Use https://shields.io/ -->
[Code style: black]:https://img.shields.io/badge/code%20style-black-000000.svg
[Requires.io]:https://img.shields.io/requires/github/ITISFoundation/osparc-simcore.svg
[travis-ci]:https://travis-ci.org/ITISFoundation/osparc-simcore.svg?branch=master
[github.io]:https://img.shields.io/website-up-down-green-red/https/itisfoundation.github.io.svg?label=documentation
[itis.dockerhub]:https://img.shields.io/website/https/hub.docker.com/u/itisfoundation.svg?down_color=red&label=dockerhub%20repos&up_color=green
[coveralls.io]:https://coveralls.io/repos/github/ITISFoundation/osparc-simcore/badge.svg?branch=master
[codecov.io]:https://codecov.io/gh/ITISFoundation/osparc-simcore/branch/master/graph/badge.svg
[license]:https://img.shields.io/github/license/ITISFoundation/osparc-simcore
[Github-CI Push/PR]:https://github.com/ITISFoundation/osparc-simcore/workflows/Github-CI%20Push/PR/badge.svg
<!------------------------------------------------------>


The SIM-CORE, named **o<sup>2</sup>S<sup>2</sup>PARC** – **O**pen **O**nline **S**imulations for **S**timulating **P**eripheral **A**ctivity to **R**elieve **C**onditions – is one of the three integrative cores of the SPARC program’s Data Resource Center (DRC).
The aim of o<sup>2</sup>S<sup>2</sup>PARC is to establish a comprehensive, freely accessible, intuitive, and interactive online platform for simulating peripheral nerve system neuromodulation/ stimulation and its impact on organ physiology in a precise and predictive manner.
To achieve this, the platform will comprise both state-of-the art and highly detailed animal and human anatomical models with realistic tissue property distributions that make it possible to perform simulations ranging from the molecular scale up to the complexity of the human body.


## Getting Started


This is the common workflow to build and deploy locally:

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

  # open front-end in the browser
  #  localhost:9081 - simcore front-end site
  #
  xdg-open http://localhost:9081/

  # stops
  make down
```

Services are deployed in two stacks:``simcore-stack`` comprises all core-services in the framework
and ``ops-stack`` is a subset of services from [ITISFoundation/osparc-ops](https://github.com/ITISFoundation/osparc-ops) used
for operations during development. This is a representation of ``simcore-stack``:

![](docs/img/.stack-simcore-version.yml.png)


### Requirements

To verify current base OS, Docker and Python build versions have a look at:
- Travis CI [config](.travis.yml)
- GitHub Actions [config](.github/workflows/ci-testing-deploy.yml)

To build and run:

- docker
- make >=4.2
- awk, jq (optional tools within makefiles)

To develop, in addition:

- python 3.6 (this dependency will be deprecated soon)
- nodejs for client part (this dependency will be deprecated soon)
- swagger-cli (make sure to have a recent version of nodejs)
- [vscode] (highly recommended)

This project works and is developed under **linux (Ubuntu recommended)**.

##### Setting up Other Operating Systems

When developing on these platforms you are on your own.

In **windows**, it works under [WSL] (windows subsystem for linux). Some details on the setup:

- [Install](https://chocolatey.org/docs/installation) [chocolatey] package manager
  - ``choco install docker-for-windows``
  - ``choco install wsl`` or using [instructions](https://docs.microsoft.com/en-us/windows/wsl/install-win10)
-  Follow **all details** on [how to setup flawlessly](https://nickjanetakis.com/blog/setting-up-docker-for-windows-and-wsl-to-work-flawlessly) docker for windows and [WSL]

In **MacOS**, [replacing the MacOS utilities with GNU utils](https://apple.stackexchange.com/a/69332) might be required.

## Releases

**WARNING** This application is **still under development**.

- [Git release workflow](ops/README.md)
- Public [releases](https://github.com/ITISFoundation/osparc-simcore/releases)
- Production in https://osparc.io
- [Staging instructions](docs/staging-instructions.md)
- [User Manual](https://itisfoundation.github.io/osparc-manual/)

## Contributing

Would you like to make a change or add something new? Please read the [contributing guidelines](CONTRIBUTING.md).


## License

This project is licensed under the terms of the [MIT license](LICENSE).


<!-- ADD REFERENCES BELOW AND KEEP THEM IN ALPHABETICAL ORDER -->
[chocolatey]:https://chocolatey.org/
[vscode]:https://code.visualstudio.com/
[WSL]:https://docs.microsoft.com/en-us/windows/wsl/faq

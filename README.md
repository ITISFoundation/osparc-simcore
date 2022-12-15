# osparc-simcore platform

<p align="center">
<img src="https://user-images.githubusercontent.com/32800795/61083844-ff48fb00-a42c-11e9-8e63-fa2d709c8baf.png" width="500">
</p>


<!-- NOTE: when branched replace `master` in urls -->
[![Code style: black]](https://github.com/psf/black)
[![CI](https://github.com/ITISFoundation/osparc-simcore/actions/workflows/ci-testing-deploy.yml/badge.svg)](https://github.com/ITISFoundation/osparc-simcore/actions/workflows/ci-testing-deploy.yml)
[![codecov](https://codecov.io/gh/ITISFoundation/osparc-simcore/branch/master/graph/badge.svg?token=h1rOE8q7ic)](https://codecov.io/gh/ITISFoundation/osparc-simcore)
[![github.io]](https://itisfoundation.github.io/)
[![itis.dockerhub]](https://hub.docker.com/u/itisfoundation)
[![license]](./LICENSE)


<!-- ADD HERE ALL BADGE URLS. Use https://shields.io/ -->
[Code style: black]:https://img.shields.io/badge/code%20style-black-000000.svg
[github.io]:https://img.shields.io/website-up-down-green-red/https/itisfoundation.github.io.svg?label=documentation
[itis.dockerhub]:https://img.shields.io/website/https/hub.docker.com/u/itisfoundation.svg?down_color=red&label=dockerhub%20repos&up_color=green
[license]:https://img.shields.io/github/license/ITISFoundation/osparc-simcore
[Github-CI Push/PR]:https://github.com/ITISFoundation/osparc-simcore/workflows/Github-CI%20Push/PR/badge.svg
[![Quality Gate Status](https://sonarcloud.io/api/project_badges/measure?project=ITISFoundation_osparc-simcore&metric=alert_status)](https://sonarcloud.io/summary/new_code?id=ITISFoundation_osparc-simcore)
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
  #  127.0.0.1.nip.io:9081 - simcore front-end site
  #
  xdg-open http://127.0.0.1.nip.io:9081/

  # stops
  make down
```

Some routes can only be reached via DNS such as `UUID.services.DNS`. Since `UUID.services.127.0.0.1` is **not a valid DNS**, the solution is to use [nip.io](https://nip.io/). A service that maps ``<anything>[.-]<IP Address>.nip.io`` in "dot", "dash" or "hexadecimal" notation to the corresponding ``<IP Address>``.

Services are deployed in two stacks:``simcore-stack`` comprises all core-services in the framework and ``ops-stack`` is a subset of services from [ITISFoundation/osparc-ops](https://github.com/ITISFoundation/osparc-ops) used for operations during development.

### Requirements

To verify current base OS, Docker and Python build versions have a look at:

- GitHub Actions [config](.github/workflows/ci-testing-deploy.yml)

To build and run:

- docker
- make >=4.2
- awk, jq (optional tools within makefiles)

To develop, in addition:

- python 3.9
- nodejs for client part (this dependency will be deprecated soon)
- swagger-cli (make sure to have a recent version of nodejs)
- [vscode] (highly recommended)

This project works and is developed under **linux (Ubuntu recommended)**.

#### Setting up Other Operating Systems

When developing on these platforms you are on your own.

In **windows**, it works under [WSL2] (windows subsystem for linux **version2**). Some details on the setup:

- Follow **all details** on [how to setup WSL2 with docker and ZSH](https://nickymeuleman.netlify.app/blog/linux-on-windows-wsl2-zsh-docker) docker for windows and [WSL2]

In **MacOS**, [replacing the MacOS utilities with GNU utils](https://apple.stackexchange.com/a/69332) might be required.

#### Upgrading services requirements

Updates are upgraded using a docker container and pip-sync.
Build and start the container:

```bash
    cd requirements/tools
    make build
    make shell
```

Once inside the container navigate to the service's requirements directory.

To upgrade all requirements run:

```bash
    make reqs
```

To upgrade a single requirement named `fastapi`run:

```bash
    make reqs upgrade=fastapi
```

## Releases

**WARNING** This application is **still under development**.

- [Git release workflow](docs/releasing-workflow-instructions.md)
- Public [releases](https://github.com/ITISFoundation/osparc-simcore/releases)
- Production in https://osparc.io
- [Staging instructions](docs/releasing-workflow-instructions.md#staging-example)
- [User Manual](https://itisfoundation.github.io/osparc-manual/)

## Contributing

Would you like to make a change or add something new? Please read the [contributing guidelines](CONTRIBUTING.md).

## License

This project is licensed under the terms of the [MIT license](LICENSE).

---

<p align="center">
<image src="https://github.com/ITISFoundation/osparc-simcore-python-client/blob/4e8b18494f3191d55f6692a6a605818aeeb83f95/docs/_media/mwl.png" alt="Made with love at www.z43.swiss" width="20%" />
</p>

<!-- ADD REFERENCES BELOW AND KEEP THEM IN ALPHABETICAL ORDER -->
[chocolatey]:https://chocolatey.org/
[vscode]:https://code.visualstudio.com/
[WSL2]:https://docs.microsoft.com/en-us/windows/wsl

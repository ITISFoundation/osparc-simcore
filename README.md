# osparc-simcore platform

<p align="center">
<img src="https://user-images.githubusercontent.com/32800795/61083844-ff48fb00-a42c-11e9-8e63-fa2d709c8baf.png" width="500">
</p>


<!-- BADGES: LINKS ON CLICK --------------------------------------------------------------->
[![black_badge]](https://github.com/psf/black)
[![ci_badge]](https://github.com/ITISFoundation/osparc-simcore/actions/workflows/ci-testing-deploy.yml)
[![codecov_badge]](https://codecov.io/gh/ITISFoundation/osparc-simcore)
[![doc_badge]](https://itisfoundation.github.io/)
[![dockerhub_badge]](https://hub.docker.com/u/itisfoundation)
[![license_badge]](./LICENSE)
[![sonarcloud_badge]](https://sonarcloud.io/summary/new_code?id=ITISFoundation_osparc-simcore)
[![osparc_status]](https://status.osparc.io)
[![s4l_status]](https://s4llite.statuspage.io)

<!-- BADGES: LINKS TO IMAGES. Default to https://shields.io/ ------------------------------>
[black_badge]:https://img.shields.io/badge/code%20style-black-000000.svg
[ci_badge]:https://github.com/ITISFoundation/osparc-simcore/actions/workflows/ci-testing-deploy.yml/badge.svg
[codecov_badge]:https://codecov.io/gh/ITISFoundation/osparc-simcore/branch/master/graph/badge.svg?token=h1rOE8q7ic
[doc_badge]:https://img.shields.io/website-up-down-green-red/https/itisfoundation.github.io.svg?label=documentation
[dockerhub_badge]:https://img.shields.io/website/https/hub.docker.com/u/itisfoundation.svg?down_color=red&label=docker%20images&up_color=blue
[license_badge]:https://img.shields.io/github/license/ITISFoundation/osparc-simcore
[sonarcloud_badge]:https://sonarcloud.io/api/project_badges/measure?project=ITISFoundation_osparc-simcore&metric=alert_status
[s4l_status]:https://img.shields.io/badge/dynamic/json?label=s4l-lite.io&query=%24.status.description&url=https%3A%2F%2Fdfrzcpn4jp96.statuspage.io%2Fapi%2Fv2%2Fstatus.json
[osparc_status]:https://img.shields.io/badge/dynamic/json?label=osparc.io&query=%24.status.description&url=https%3A%2F%2Fstatus.osparc.io%2Fapi%2Fv2%2Fstatus.json
<!------------------------------------------------------------------------------------------>


The SIM-CORE, named **o<sup>2</sup>S<sup>2</sup>PARC** – **O**pen **O**nline **S**imulations for **S**timulating **P**eripheral **A**ctivity to **R**elieve **C**onditions – is one of the three integrative cores of the SPARC program’s Data Resource Center (DRC).
The aim of o<sup>2</sup>S<sup>2</sup>PARC is to establish a comprehensive, freely accessible, intuitive, and interactive online platform for simulating peripheral nerve system neuromodulation/ stimulation and its impact on organ physiology in a precise and predictive manner.
To achieve this, the platform will comprise both state-of-the art and highly detailed animal and human anatomical models with realistic tissue property distributions that make it possible to perform simulations ranging from the molecular scale up to the complexity of the human body.

## Getting Started

A production instance of **o<sup>2</sup>S<sup>2</sup>PARC** is running at [oSPARC.io](https://osparc.io). 

If you want to spin up your own instance, you can follow the common workflow to build and deploy locally using the **Linux commandline** (Ubuntu recommended). 
Make sure you first install all the [requirements](#Requirements) mentioned in the section below.

```bash
  # clone code repository
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

To build and run:

- git
- docker
- make >=4.2
- awk, jq (optional tools within makefiles)

To develop, in addition:

- python 3.10
- nodejs for client part (this dependency will be deprecated soon)
- swagger-cli (make sure to have a recent version of nodejs)
- [vscode] (highly recommended)

To verify current base OS, Docker and Python build versions have a look at:

- GitHub Actions [config](.github/workflows/ci-testing-deploy.yml)

If you want to verify if your system has all the necessary requirements:

```bash
    make info
```


#### Setting up other Operating Systems

When developing on these platforms you are on your own.

On **Windows**, it works under [WSL2] (Windows Subsystem for Linux **version2**). Some details on the setup:

- Follow **all details** on [how to setup WSL2 with docker and ZSH](https://nickymeuleman.netlify.app/blog/linux-on-windows-wsl2-zsh-docker) docker for windows and [WSL2]

**MacOS** is currently not supported.

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
<image src="https://raw.githubusercontent.com/ITISFoundation/osparc-simcore-clients/4e8b18494f3191d55f6692a6a605818aeeb83f95/docs/_media/mwl.png" alt="Made with love (and lots of hard work) at www.z43.swiss" width="20%" />
</p>

<!-- ADD REFERENCES BELOW AND KEEP THEM IN ALPHABETICAL ORDER -->
[chocolatey]:https://chocolatey.org/
[vscode]:https://code.visualstudio.com/
[WSL2]:https://docs.microsoft.com/en-us/windows/wsl

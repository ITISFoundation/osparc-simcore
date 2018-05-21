# osparc-simcore platform

[![Build Status](https://travis-ci.org/ITISFoundation/osparc-simcore.svg?branch=master)](https://travis-ci.org/ITISFoundation/osparc-simcore)

## Overview

[![service-web](docs/img/service-web.svg)](http://interactive.blockdiag.com/?compression=deflate&src=eJxdjs0KwjAQhO99imXPFtNbpcYXkR7ys2hw6UqSKiK-uymxiF7nm28Yy-IuPpgTPBsAvJPdOg40ZYRjOpsr6UkyjUOB_tEmirfgKH0YaEDHMnsshX993x5qsEgUyx4bS6x3qu824IQlastz3f4pFtGHSC5LXCXsleqw3ljRUvteGprXG1PtQR0)


```bash
  git clone git@github.com:ITISFoundation/osparc-simcore.git
  cd ospacr-simcore

  # build service images
  make build
  
  # deploy
  make up

  # to stop deployed services
  make down
```


## Development

- To run linters in host machine

```bash
  make pylint
```

# Management of releases of simcore

The process of creating staging/release/hotfix versions of code from [Master](https://github.com/ITISFoundation/osparc-simcore/tree/master) is described here.

## Description

Each commit on the master branch triggers a CI workflow that build the simcore platform docker images. These docker images are then stored in [dockerhub](https://hub.docker.com/repositories/itisfoundation).
Each docker image are named following this pattern:
  - itisfoundation/[image_name]:master-[CINAME]-latest
  - itisfoundation/[image_name]:master-[CINAME]-[BUILD_DATE]--[BUILD_TIME].[GIT_SHA]

For example, the ``webserver`` service in master branch with commit ``752ef...`` will be built by ``github`` actions CI on ``2020/08/31`` at ``12:36`` and therefore the image is named as:
  - ``itisfoundation/webserver:master-github-v2.0.1-2020-08-31--12-36.752ef50f3babb6537580c0e03b85b9a8209bbf10``
  - ``itisfoundation/webserver:master-github-latest``

## Staging process

A staging version of simcore is like a pre-released version, that is marked as such on the master branch by leveraging Github pre-release tagging mechanism. The CI is triggered and will pull the marked docker images, and tag them as staging images.
Each docker image are renamed as:
- itisfoundation/[image_name]:staging-[CINAME]-latest
- itisfoundation/[image_name]:staging-[CINAME]-staging_[BUILD_NAMEVERSION]-[BUILD_DATE]--[BUILD_TIME].[GIT_SHA]

For example, just before the review of the ``DAJIA`` sprint we release a staging version ``v1.0.0`, the commit ``752ef...`` from above is tagged as stage and the ``github`` actions CI on ``2020/09/01`` at ``17:30``.
  - ``itisfoundation/webserver:staging-github-DAJIAv1.0.0-2020-09-01--17-30.752ef50f3babb6537580c0e03b85b9a8209bbf10``
  - ``itisfoundation/webserver:staging-github-latest``
 
then after the review we do a couple of additions and re-release staging ``DAJIA`` sprint  as `v1.1.0`
  - ``itisfoundation/webserver:staging-github-DAJIAv1.1.0-2020-09-01--20-30.560eq50f3babb6537580c0e03b85b9a8209bbf10``
  - ``itisfoundation/webserver:staging-github-latest``
  
  
### Instructions

1. Generate Github release tag

  ```bash
  git clone https://github.com/ITISFoundation/osparc-simcore.git
  cd osparc-simcore
  make release-staging name=SPRINTNAME version=VERSION (git_sha=OPTIONAL)
  ```

2. Adjust the list of changes if needed
3. Press the **Publish release** button
4. The CI will be automatically triggered and will deploy the staging release

## Release process

A released version of simcore, that is marked as such on the master branch by leveraging Github release tagging mechanism. The CI is triggered and will pull the marked staging docker images, and tag them as release images.
**NOTE:** A release version is ALWAYS preceded by a staging version. The CI will fail if it does not find the corresponding staging version.
Each docker build marked as released are tagged as:
- itisfoundation/[image_name]:release-[CINAME]-latest
- itisfoundation/[image_name]:release-[CINAME]-v[BUILD_VERSION]-[BUILD_DATE]--[BUILD_TIME].GIT_SHA

As example, the team decides to release to production the lastest staging version of ``DAJIA`` sprint. Next release version, following semantic versioning and previous releases, is `v5.6.0`. The images will be retaged by github actions CI as:
  - ``itisfoundation/webserver:release-github-v5.6.0-2020-09-02--19-30.560eq50f3babb6537580c0e03b85b9a8209bbf10``
  - ``itisfoundation/webserver:release-github-latest``

### Instructions

1. Generate Github release tag

  ```bash
  git clone https://github.com/ITISFoundation/osparc-simcore.git
  cd osparc-simcore
  make release-prod version=MAJ.MIN.PATCH (git_sha=OPTIONAL)
  ```

2. Adjust the list of changes if needed
3. Press the **Publish release** button
4. The CI will be automatically triggered and will deploy the staging release

## Hotfix process

A hotfix is **ALWAYS made from an already released version**. 
Each docker build marked as released are tagged as:
- itisfoundation/[image_name]:release-[CINAME]-latest
- itisfoundation/[image_name]:release-[CINAME]-v[BUILD_VERSION]-[BUILD_DATE]--[BUILD_TIME].[GIT_SHA]

### Instructions

1. Generate Github release tag

  ```bash
  git clone https://github.com/ITISFoundation/osparc-simcore.git
  cd osparc-simcore
  git checkout VERSION_TAG_FOR_HOTFIXING
  # make the fix through usual PR process
  make release-hotfix version=MAJ.MIN.PATCH (git_sha=OPTIONAL)
  ```

2. Adjust the list of changes if needed
3. Press the **Publish release** button
4. The CI will be automatically triggered and will deploy the staging release

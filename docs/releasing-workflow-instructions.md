# Management of releases of simcore

The process of creating staging/release/hotfix versions of code from [Master](https://github.com/ITISFoundation/osparc-simcore/tree/master) is described here.

## Description

Each commit on the master branch triggers a CI workflow that build the simcore platform docker images. These docker images are then stored in [dockerhub](https://hub.docker.com/repositories/itisfoundation).
Each docker build are tagged as:
  - itisfoundation/[image_name]:master-[CINAME]-latest
  - itisfoundation/[image_name]:master-[CINAME]-[BUILD_DATE]--[BUILD_TIME].GIT_SHA

## Staging process

A staging version of simcore is like a pre-released version, that is marked as such on the master branch by leveraging Github pre-release tagging mechanism. The CI is triggered and will pull the marked docker images, and tag them as staging images.
Each docker build marked as staged are tagged as:
- itisfoundation/[image_name]:staging-[CINAME]-latest
- itisfoundation/[image_name]:staging-[CINAME]-staging_[BUILD_NAMEVERSION]-[BUILD_DATE]--[BUILD_TIME].GIT_SHA

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

A Hotfix is ALWAYS made from an already released version.
Each docker build marked as released are tagged as:
- itisfoundation/[image_name]:release-[CINAME]-latest
- itisfoundation/[image_name]:release-[CINAME]-v[BUILD_VERSION]-[BUILD_DATE]--[BUILD_TIME].GIT_SHA

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

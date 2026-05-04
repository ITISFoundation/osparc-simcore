# project migration

Built on top of the existing `postgres-database` package.

It is used to migrate a user's project. Currently, this does not work for hidden projects, generated via the api.

It uses low-level direct access to pgSQL and S3. Data sync is done using `rclone`. Therefore, this script might become outdated upon database changes in osparc-simcore.


# Maintainers:
ANE, DK

# How to use

1. Build the image locally

```
make build
```

2. **Optional**  Create an empty configuration file. Fill up the file `cfg.json` with data. Also refer to `src/models.py` on how to fill up the file.

```
make cfg.json
```

3. Finally start the migration


**NOTE: Due to simcore-storage service actively garbage-colelting dangling multipart upload links, you need to scale storage to 0 when running this script.** (You will get errors with multipart uploads if since storage will try to remove the files If this is no longer the case please remove this message.)

```
make migrate
```

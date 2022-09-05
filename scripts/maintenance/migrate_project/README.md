# project migration

Built on top of the existing `postgres-database` package.

It is used to migrate a user's project. Currently, this does not work for hidden projects, generated via the api.

It uses low-level direct access to pgSQL and S3. Data sync is done using `rclone`. Therefore, this script might become outdated upon database changes in osparc-simcore.


# TIP - What to do before you run the script:
1. Make sure the storage microservice of simcore will not garbage-collect multipart-upload-links while this script is running. For example, pause the storage microservice or set the garbage colelction interval very high.
2. Create a valid `cfg.json`. To get a template for this, run `make cfg.template.json`

# IMPORTANT PITFALLS:
- Currently, this does not work for hidden projects, generated via the api.
- No postgres database version migration is performed atm. This migration only works for identical source and target RDBs.
- If a file's or project's UUID already exist in the destination database (colision), this script will fail with an error.
- Supported S3 providers are `CEPH`, `AWS`, `MINIO`


# Maintainers:
ANE, DK

# How to use

1. Build the image locally

```
make build
```

Create a configuration file

```
make cfg.template.json
```

Fill up the file `cfg.json` with data. Also refer to `src/models.py` on how to fill up the file.

Finally start the process


**NOTE: Due to simcore-storage service actively garbage-colelting dangling multipart upload links, you might want to scale storage to 0 when running this script.** (You will get errors with multipart uploads if since storage will try to remove the files If this is no longer the case please remove this message.)
```
make migrate
```

This operation might take a bit.



### Possible future enhancements:
- Assign new random UUIDv6() during copying to prevent clashes and allow flexible duplicate-copying of projects
- Integrate Postgres Migration (allow copying with down/upgrade)
- Allow retry if copying fails (e.g. due to network issues): Check if files already present are identical, if so, continue

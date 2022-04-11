# project migration

Built on top of the existing `postgres-database` package.
It is used to migrate a user's project and eventually (hidden projects, generated via the api).

If a file's or project's unique identifier already exist in the destination database, the process will not continue.

**NOTE:** data sync is done using `rclone`, currently it is assumed that the data source is a `MINIO S3 backend` and the destination is an `AWS S3 backend`.


Any doubts? Ask **ANE**.
# How to use

Build the image locally

```
make build
```

Create a configuration file 

```
make empty-config-file 
```

Fill up the `cfg.json` with data. Also refer to `src/models.py` on how to fill up the file.

Finally start the process

```
make migrate
```

It will copy 1 file at a time, so this operation might take a bit.

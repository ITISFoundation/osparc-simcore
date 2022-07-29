# how to use consistency check with a deployment

```bash
cd osparc-simcore

cd packages/postgres-database
# this imports the database of master in a local volume
make import-db-from-docker-volume host=DOCKER_HOST_NAME host_volume=DB_VOLUME_NAME local_volume=LOCAL_VOLUME_NAME

cd -
cd scripts/maintenance
make
./check_consistency_data.py LOCAL_VOLUME_NAME DB_USERNAME DB_PSSWORD S3_ENDPOINT S3_ACCESS S3_SECRET S3_BUCKET
```

# osparc-simcore -> ancillary

Each folder contains files relevant to the _building_ of services that are ancillary to the
osparc application platform.  These services are not a core part of osparc, but may be relied
upon by osparc in some situations.  (e.g. S3 storage service, Docker registry...) In other
situations these services might be provided by external sources (e.g. AWS, GCE)

Deployment is done via Ansible in the 'ops' folder...
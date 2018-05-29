# osparc-simcore -> ops -> ansible -> roles -> minio

Ansible role for minio S3 compatible storage server

After deployment, minio service is available on http://{{ hostvars[groups['managers'][0]].ansible_host }}:10001
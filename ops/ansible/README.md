## osparc-simcore -> ops -> ansible

__Ansible deployment roles & playbooks__

* Follow [Ansible playbooks structure best practices](http://docs.ansible.com/ansible/latest/user_guide/playbooks_best_practices.html)
* Reference [Ansible container roles best practices](https://docs.ansible.com/ansible-container/roles/writing.html)

### Ansible Minimal Prerequisites

The following are the minimum requirements for using Ansible:

1. Ansible package installed on host from which you run these playbooks
1. SSH public key for your control host is installed into `/home/ans/.ssh/authorized_keys` on every host you intend to control
1. An entry has been added to `~/.ssh/known_hosts` on your control host for every remote host you intend to control.
1. package `python-minimal` or equivilent python installed on every remote host you intend to control.
1. package `python-apt` installed on remote hosts (to allow `apt` module)

### Example deployment

From internal ansible control host: 

```
ans@ansible:~/Repositories/github.com/ehzastrow/osparc-simcore/ops/ansible$ ansible-playbook -i testing ancillary-minio.yml
```
# Admin Grafana Dashboards


## Description

Ansible Role meant to be executed by Cluster Admins in order to deploy custom Grafana Dashboards and their associated
data sources.


## Role Variables

- `oc`: oc binary shortcut for production use when running from the bastion host.

- `oc_dev`: oc binary shortcut for development or when running as admin from another jump-host or laptop.

- `templates_path`: The destination path for templates once they've been populated.

- `dashboards`: List. Names of dashboards to deploy.

- `es_tls_cacert`: String. CA Cert from ElasticSearch secret. This gets auto-populated by the tasks.

- `es_tls_clientcert`: String. Client Cert from ElasticSearch secret. This gets auto-populated by the tasks.

- `es_tls_clientkey`: String. Client Key from ElasticSearch secret. This gets auto-populated by the tasks.

- `state`: String. Valid inputs are empty string and `'absent'`. If `state` is `'absent'` resources will be removed.


## Example Playbook

```
---
- hosts: localhost 
  gather_facts: false
  become: false
  vars_files:
    - vars/installer-vault.yml
  tasks:
    - import_role: 
        name: ot1_vault
        tasks_from: login
    - import_role:
        name: ot1_vault
        tasks_from: get_ocp_install_secrets

- hosts: localhost
  become: false
  gather_facts: false
  roles:
    - role: ot1_grafana
...
```

## License

All rights reserved.

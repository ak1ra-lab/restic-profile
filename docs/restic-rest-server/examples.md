# restic-rest-server examples

This page is the recommended starting point when you deploy
`restic_rest_server` with Ansible.

Use this page together with:

- [ansible.md](ansible.md) for role behavior, binary detection, and operational notes

## Minimal playbook

```yaml
# playbooks/restic-rest-server.yaml
---
- name: manage restic-rest-server
  hosts: backup_servers
  gather_facts: false
  become: true

  tasks:
    - name: apply restic_rest_server role
      ansible.builtin.import_role:
        name: restic_rest_server
```

## Scenario 1: append-only server with private repositories

```yaml
# host_vars/backup-server-01/restic-rest-server.yaml
---
restic_rest_server_listen: ":8000"
restic_rest_server_append_only: true
restic_rest_server_private_repos: true
restic_rest_server_backup_dir: /srv/restic

# Keep credentials in Vault.
restic_rest_server_htpasswd_users:
  - name: alice
    password: "{{ vault_restic_rest_server_alice_password }}"
  - name: bob
    password: "{{ vault_restic_rest_server_bob_password }}"
```

With `private_repos: true`, each user writes below `/srv/restic/<username>/...`.
This is the most common deployment shape for multi-tenant backup storage.

## Scenario 2: reverse-proxy fronted service

```yaml
# host_vars/backup-server-02/restic-rest-server.yaml
---
# Bind only on localhost and let nginx/Caddy/Traefik handle TLS in front.
restic_rest_server_listen: "127.0.0.1:8000"
restic_rest_server_append_only: true
restic_rest_server_private_repos: true
restic_rest_server_backup_dir: /srv/restic

restic_rest_server_htpasswd_users:
  - name: alice
    password: "{{ vault_restic_rest_server_alice_password }}"
```

Clients still use an HTTPS `rest:` repository URL that points at the reverse
proxy, not at the loopback listen address shown here.

## Scenario 3: same host with server-side prune via standalone restic-profile

When `append_only: true`, clients cannot run `forget` or `prune` through the
REST API. Schedule retention on the repository host with the standalone
`restic-profile` project instead. That project now owns the inventory schema,
role, and timer examples for retention-only profiles.

## Debian 12 note

On Debian 12 and other environments where the package is unavailable, keep the
same inventory variables and place the binary at
`/usr/local/bin/restic-rest-server`. The role starts the service automatically on
subsequent runs once that path exists.

# restic-rest-server

Ansible role to deploy [rest-server](https://github.com/restic/rest-server) — the
REST backend for restic repositories. Manages binary installation, systemd
service, and htpasswd-based authentication.

See `roles/restic_rest_server/defaults/main.yaml` for all variables.

## Minimal playbook

```yaml
---
- name: deploy restic-rest-server
  hosts: backup_servers
  gather_facts: false
  become: true
  tasks:
    - ansible.builtin.import_role:
        name: ak1ra_lab.restic_profile.restic_rest_server
```

## Example 1: basic append-only server

```yaml
restic_rest_server_listen: ":8000"
restic_rest_server_backup_dir: /srv/restic
restic_rest_server_append_only: true
restic_rest_server_private_repos: true

restic_rest_server_htpasswd_users:
  - name: alice
    password: "{{ vault_alice_password }}"
  - name: bob
    password: "{{ vault_bob_password }}"
```

Backup clients connect to `https://backup.example.com:8000/alice/<repo-name>`.

## Example 2: go_build on a Debian 12 host

```yaml
restic_rest_server_binary_install_source: go_build
restic_rest_server_binary_install_path: /usr/local/bin/restic-rest-server
restic_rest_server_listen: ":8000"
restic_rest_server_backup_dir: /srv/restic
```

Use `go_build` when the distro package isn't available (e.g. Debian 12).
On Debian 13+ the package is available via `apt`.

## Retention on the repository host

When `append_only: true`, clients can create snapshots but cannot run `forget` or
`prune`. Deploy a retention-only profile with the `restic_profile` role on the
same host, pointing at the local repository path:

```yaml
# On the backup server, in addition to restic_rest_server:
restic_profile_repositories:
  r1:
    repository: "/srv/restic/alice/myapp"
    password: "{{ vault_alice_restic_password }}"

restic_profile_profiles:
  alice-myapp-retention:
    repository_ref: r1
    tag: "myapp"
    on_calendar: "daily"
    retention:
      forget_current_host: false
      prune: true
      keep_daily: 14
      keep_weekly: 8
      keep_monthly: 12
```

## Key variables

| Variable                                   | Default                                    | Notes                            |
| ------------------------------------------ | ------------------------------------------ | -------------------------------- |
| `restic_rest_server_listen`                | `":8012"`                                  | Listen address                   |
| `restic_rest_server_backup_dir`            | `"/srv/restic"`                            | Storage root                     |
| `restic_rest_server_append_only`           | `true`                                     | Disallow forget/prune via REST   |
| `restic_rest_server_private_repos`         | `true`                                     | Subdirectories are private repos |
| `restic_rest_server_htpasswd_file`         | `"/etc/restic-rest-server/users.htpasswd"` |                                  |
| `restic_rest_server_binary_install_source` | `"apt"`                                    | `apt` / `go_build` / `existing`  |
| `restic_rest_server_htpasswd_crypt_scheme` | `"bcrypt"`                                 | Strongly recommended             |

Htpasswd users require `python3-passlib` + `python3-bcrypt` on the managed node
(installed automatically by the role).

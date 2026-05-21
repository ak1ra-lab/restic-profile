# restic-rest-server with Ansible

If you are starting from inventory, begin with [examples.md](examples.md). This
page focuses on what the role manages and what it validates.

## Role: restic_rest_server

The `restic_rest_server` role:

1. Validates listen, user, and group inputs plus every non-empty htpasswd user entry.
2. Installs `restic`, `python3-passlib`, and `python3-bcrypt` via APT.
3. Attempts to install `restic-rest-server` via APT.
4. Detects the server binary at `/usr/bin/restic-rest-server` or `/usr/local/bin/restic-rest-server`.
5. Creates the configured system user and group.
6. Manages `/etc/restic-rest-server/users.htpasswd`.
7. Renders `/etc/default/restic-rest-server`.
8. Renders a custom systemd unit only when the binary is not APT-managed.
9. Enables and starts the service when the binary is present.

## Binary detection

`restic-rest-server` is packaged in Debian starting from Debian 13 (trixie).
The role checks both supported locations and prefers the APT-managed binary when
both exist.

| Path                                | Source                 | Priority  |
| ----------------------------------- | ---------------------- | --------- |
| `/usr/bin/restic-rest-server`       | Debian package         | Preferred |
| `/usr/local/bin/restic-rest-server` | Manually placed binary | Fallback  |

If neither path exists, the role still creates the user, htpasswd file, and
`/etc/default/restic-rest-server`. It also deploys the custom systemd unit, but
it does not start the service and instead emits an operator reminder.

## Role inputs

The authoritative defaults live in `roles/restic_rest_server/defaults/main.yaml`.
These are the inputs you will usually override from inventory:

- `restic_rest_server_listen`: TCP listen address such as `":8000"` or `"127.0.0.1:8000"`
- `restic_rest_server_append_only`: pass `--append-only` so clients cannot delete snapshots
- `restic_rest_server_private_repos`: pass `--private-repos` so each user gets an isolated subdirectory
- `restic_rest_server_backup_dir`: local repository root passed to `--path`
- `restic_rest_server_htpasswd_users`: declarative htpasswd user list
- `restic_rest_server_htpasswd_file`: htpasswd file location
- `restic_rest_server_htpasswd_crypt_scheme`: password hashing scheme, `bcrypt` by default
- `restic_rest_server_extra_args`: extra arguments appended to the server command line
- `restic_rest_server_user` and `restic_rest_server_group`: service account and group

## Managed files

| Path                                             | Purpose                                              |
| ------------------------------------------------ | ---------------------------------------------------- |
| `/etc/default/restic-rest-server`                | Environment file consumed by the service             |
| `/etc/restic-rest-server/users.htpasswd`         | Managed Basic Auth credentials                       |
| `/etc/systemd/system/restic-rest-server.service` | Custom unit, only when the binary is not APT-managed |

`restic_rest_server_backup_dir` defaults to `/srv/restic` and is passed to the
daemon as `--path`, but the role does not currently manage that directory as a
separate filesystem resource.

## Validation checks

Before it manages files, the role asserts that:

1. `restic_rest_server_listen` is a non-empty string.
2. `restic_rest_server_user` is a non-empty string.
3. `restic_rest_server_group` is a non-empty string.
4. Every `restic_rest_server_htpasswd_users` entry with a non-empty `name` also has a non-empty `password`.

## Service behavior

- If the binary is present, the role enables and starts `restic-rest-server.service`.
- If the binary is absent, the role does not fail, but it does not start the service either.
- The role does not currently implement a `state: absent` teardown path.

## Security and TLS

The custom systemd unit includes hardening options such as `NoNewPrivileges=yes`,
`ProtectSystem=full`, `PrivateTmp=yes`, and a restricted `SystemCallFilter`.

The htpasswd file is written as `0640` and owned by `root` plus the configured
service group so the daemon can read it without making it world-readable.

`restic-rest-server` does not terminate TLS itself. Run it behind a reverse
proxy such as nginx, Caddy, or Traefik and point clients at the HTTPS endpoint.
If the proxy uses a private CA, configure restic clients with `RESTIC_CACERT` or
with `cacert` in a standalone `restic-profile` profile.

## Operational notes

To inspect the running service:

```shell
systemctl status restic-rest-server
journalctl -u restic-rest-server -f
```

To manage users outside Ansible:

```shell
htpasswd -B /etc/restic-rest-server/users.htpasswd alice
htpasswd -D /etc/restic-rest-server/users.htpasswd alice
```

Manual htpasswd edits may be overwritten on the next Ansible run if the same
user is also present in `restic_rest_server_htpasswd_users`.

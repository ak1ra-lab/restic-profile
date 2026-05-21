# restic-rest-server

`restic-rest-server` is the official HTTP backend for
[restic](https://restic.net/). It exposes a repository over HTTP(S), allowing
restic clients to back up to a central server using the `rest:` URL scheme.

The recommended deployment path in this repository is the
`restic_rest_server` Ansible role. It manages the daemon, the htpasswd file,
and the environment file consumed by the service.

## Configuration flow

```text
host_vars / group_vars
  -> restic_rest_server_* vars
  -> roles/restic_rest_server
      |- /etc/default/restic-rest-server
      |- /etc/restic-rest-server/users.htpasswd
      `- restic-rest-server.service
  -> optional reverse proxy / TLS termination
  -> restic clients (rest: URL) or standalone restic-profile on the same host
```

## How it works

```text
restic client (backup host)
  RESTIC_REPOSITORY="rest:https://backup.example.com/"
  RESTIC_REST_USERNAME="alice"
  RESTIC_REST_PASSWORD="secret"
        |
        |  HTTPS (HTTP Basic Auth)
        v
restic-rest-server (storage host)
  --path        /srv/restic
  --listen      :8000
  --append-only
  --private-repos
  --htpasswd-file /etc/restic-rest-server/users.htpasswd
        |
        `- /srv/restic/
              `- alice/
                    `- myapp/
```

With `--append-only`, clients can create snapshots but cannot run `forget` or
`prune`. A separate retention-only profile managed by the standalone
`restic-profile` project on the same host can perform server-side retention by
accessing the repository directly on the local filesystem.

## Start here

- Inventory and host examples: [examples.md](examples.md)
- Role behavior, binary detection, and operational notes: [ansible.md](ansible.md)

## Packaging note

`restic-rest-server` is packaged in Debian starting from Debian 13 (trixie).
On earlier releases, place the binary at `/usr/local/bin/restic-rest-server`.
The role detects both locations and starts the service automatically once one of
them exists.

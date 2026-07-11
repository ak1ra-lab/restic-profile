# restic-profile

Profile-based [restic](https://restic.net/) wrapper — Python CLI + Ansible roles.

- **restic-profile** CLI: reads a TOML config, runs `restic backup` / `forget` / `prune` with hooks and IM notifications.
- **restic_profile** Ansible role: deploys the CLI, renders TOML config, manages one systemd timer per profile.
- **restic_rest_server** Ansible role: deploys a [rest-server](https://github.com/restic/rest-server) instance for remote backup storage.

## Install

### Standalone CLI (no Ansible, no root, no systemd)

```shell
uv tool install restic-profile-cli
```

Then write your config — start from the [TOML config template](restic-profile/toml-config.md) —
and run interactively:

```shell
restic-profile -c /path/to/my.toml --check
restic-profile -c /path/to/my.toml myprofile
restic-profile -c /path/to/my.toml myprofile -n
```

No systemd timers are involved; you call the CLI yourself or wrap it in cron.

### Ansible deployment

This repo is an Ansible collection. Clone it under the standard namespace layout:

```shell
mkdir -p collections/ansible_collections/ak1ra_lab
cd collections/ansible_collections/ak1ra_lab
git clone https://github.com/ak1ra-lab/restic-profile.git restic_profile
```

The role depends on the **ak1ra_lab.general.pyproject_install** role. Install it
alongside:

```shell
cd collections/ansible_collections/ak1ra_lab
git clone https://github.com/ak1ra-lab/ansible-collection-general.git general
```

Or install dependencies via `ansible-galaxy`:

```shell
ansible-galaxy collection install -r requirements.yml
```

The bundled `ansible.cfg` needs the repo exactly 4 directory levels deep
(`collections/ansible_collections/ak1ra_lab/restic_profile/ansible.cfg`). If
your checkout path differs, adjust `collections_path` in `ansible.cfg`.

Now pick an example from [restic-profile examples](restic-profile/examples.md)
and fill in your host_vars.

## Pages

| You want to...                              | Start here                                            |
| ------------------------------------------- | ----------------------------------------------------- |
| Deploy backup profiles with Ansible         | [Ansible examples](restic-profile/examples.md)        |
| Write a TOML config for use without Ansible | [TOML config template](restic-profile/toml-config.md) |
| Understand CLI flags                        | [CLI reference](restic-profile/cli.md)                |
| Deploy a backup server (rest-server)        | [restic-rest-server](restic-rest-server.md)     |

See `roles/restic_profile/defaults/main.yaml` for all role variables and their defaults.

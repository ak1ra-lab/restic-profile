# restic-profile

Profile-based [restic](https://restic.net/) wrapper, deployed with Ansible.

This project is an Ansible collection (`ak1ra_lab.restic_profile`) that installs
and configures the `restic-profile` CLI on local or remote hosts:

- **restic-profile** CLI — reads a TOML config and runs `restic backup` /
  `forget` / `prune` with hooks and IM notifications.
- **restic_profile** role — deploys the CLI, renders the TOML config, and manages
  one systemd timer per profile (including user-level `systemd_scope: user`).
- **restic_rest_server** role — deploys a [rest-server](https://github.com/restic/rest-server)
  instance for remote backup storage.

## Deploy with Ansible

You need Ansible on the control node — see [Ansible toolchain](ansible-toolchain.md)
for a uv-based setup. Clone the repo and install this collection with its
dependencies into the project-local tree:

```shell
git clone https://github.com/ak1ra-lab/restic-profile.git
cd restic-profile
ansible-galaxy collection install -r requirements.yaml -p ./.ansible/collections
ansible-galaxy collection install --force --collections-path .ansible/collections .
```

Then pick an example from [restic-profile examples](restic-profile/examples.md)
and fill in your host_vars. Building restic from source
(`restic_profile_restic_install_source: go_build`) also needs a `go` toolchain on
the control node.

## Standalone CLI (without Ansible)

The CLI is also published on PyPI for manual or cron-driven use — no Ansible,
root, or systemd required:

```shell
uv tool install restic-profile-cli
restic-profile -c /path/to/my.toml --check
restic-profile -c /path/to/my.toml myprofile
```

Start from the [TOML config template](restic-profile/toml-config.md).

## Pages

| You want to...                              | Start here                                            |
| ------------------------------------------- | ----------------------------------------------------- |
| Deploy backup profiles with Ansible         | [Ansible examples](restic-profile/examples.md)        |
| Set up the Ansible toolchain                | [Ansible toolchain](ansible-toolchain.md)             |
| Write a TOML config for use without Ansible | [TOML config template](restic-profile/toml-config.md) |
| Understand CLI flags                        | [CLI reference](restic-profile/cli.md)                |
| Deploy a backup server (rest-server)        | [restic-rest-server](restic-rest-server.md)           |

See `roles/restic_profile/defaults/main.yaml` for all role variables and their defaults.

# restic-profile

**English** | [简体中文](README.zh-CN.md)

[![GitHub Actions Workflow Status](https://img.shields.io/github/actions/workflow/status/ak1ra-lab/restic-profile/.github%2Fworkflows%2Fpublish-to-pypi.yaml)](https://github.com/ak1ra-lab/restic-profile/actions/workflows/publish-to-pypi.yaml)
[![PyPI - Version](https://img.shields.io/pypi/v/restic-profile-cli)](https://pypi.org/project/restic-profile-cli/)
[![PyPI - Version](https://img.shields.io/pypi/v/restic-profile-cli?label=test-pypi&pypiBaseUrl=https%3A%2F%2Ftest.pypi.org)](https://test.pypi.org/project/restic-profile-cli/)
[![Docs](https://img.shields.io/badge/docs-online-0a7ea4)](https://ak1ra-lab.github.io/restic-profile/)

Profile-based restic wrapper, deployed with Ansible.

This repository is an Ansible collection (`ak1ra_lab.restic_profile`) that
installs and configures the `restic-profile` CLI on local or remote hosts:

- **restic-profile** CLI - reads a TOML config and runs `restic backup` /
  `forget` / `prune` with hooks and IM notifications.
- **restic_profile** role - deploys the CLI, renders the TOML config, and
  manages one systemd timer per profile (including user-level `systemd_scope: user`).
- **restic_rest_server** role - deploys a [rest-server][rs] instance for remote
  backup storage.

## Deploy with Ansible

You need Ansible on the control node - see [Ansible toolchain](docs/ansible-toolchain.md)
for a uv-based setup. Clone the repo and install this collection with its
dependencies into the project-local tree:

```shell
git clone https://github.com/ak1ra-lab/restic-profile.git
cd restic-profile
ansible-galaxy collection install --collections-path .ansible/collections -r requirements.yaml
ansible-galaxy collection install --force --collections-path .ansible/collections .
```

Then pick an example from [Ansible examples](docs/restic-profile/examples.md),
fill in your host_vars, and run the playbook. Building restic from source
(`restic_profile_restic_install_source: go_build`) also needs a `go` toolchain on
the control node.

## Development

Only needed to work on `src/restic_profile` or the roles and plugins:

```shell
uv sync --group dev
just lint
just typecheck
just test
ansible-lint
```

To develop `ak1ra_lab.general` alongside this repo, clone
[ansible-collection-general][acg] next to this checkout and run
`just ansible-collection-install` - it installs this collection plus your local
`../ansible-collection-general` (skipping `ansible.posix`/`community.general`,
which come from your user-level Ansible).

## Documentation

<https://ak1ra-lab.github.io/restic-profile/> - configuration lives in `mkdocs.yml`.

[rs]: https://github.com/restic/rest-server
[acg]: https://github.com/ak1ra-lab/ansible-collection-general

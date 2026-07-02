# restic-profile

[![GitHub Actions Workflow Status](https://img.shields.io/github/actions/workflow/status/ak1ra-lab/restic-profile/.github%2Fworkflows%2Fpublish-to-pypi.yaml)](https://github.com/ak1ra-lab/restic-profile/actions/workflows/publish-to-pypi.yaml)
[![PyPI - Version](https://img.shields.io/pypi/v/restic-profile)](https://pypi.org/project/restic-profile/)
[![PyPI - Version](https://img.shields.io/pypi/v/restic-profile?label=test-pypi&pypiBaseUrl=https%3A%2F%2Ftest.pypi.org)](https://test.pypi.org/project/restic-profile/)
[![Docs](https://img.shields.io/badge/docs-online-0a7ea4)](https://ak1ra-lab.github.io/restic-profile/)

Profile-based restic wrapper with Ansible deployment support.

Repository for the `restic-profile` Python CLI plus Ansible roles for
`restic-profile` and `restic-rest-server` deployments.

## Installation

```shell
uv sync --group dev
```

## Optional Ansible Tooling

For Ansible role work, install the toolchain once at user level:

```shell
uv tool install ansible-dev-tools --with ansible \
	--with-executables-from ansible-builder,ansible-core,ansible-creator,ansible-dev-environment,ansible-lint,ansible-navigator,ansible-sign,molecule
```

Routine Ansible validation currently uses `ansible-lint`. Molecule scenarios remain in the repository as dormant assets and are not part of the supported validation loop.

If you use `roles/go_build` or the playbooks under `playbooks/go_build/`, the
control node also needs a working `go` toolchain in `PATH`.

## Repository Development Workflow

Clone collections into the `ansible_collections/ak1ra_lab/` namespace layout:

```shell
mkdir -p ~/code/github.com/ansible/collections/ansible_collections/ak1ra_lab
git clone https://github.com/ak1ra-lab/ansible-collection-general.git \
	~/code/github.com/ansible/collections/ansible_collections/ak1ra_lab/general
git clone https://github.com/ak1ra-lab/restic-profile.git \
	~/code/github.com/ansible/collections/ansible_collections/ak1ra_lab/restic_profile
```

## Usage

```shell
uv run restic-profile --help
```

For Ansible-managed backup servers, see the `restic_rest_server` role and the
documentation under `docs/restic-rest-server/`.

## Development

```shell
just lint
just typecheck
just test
just docs-build
ansible-lint
```

## Documentation

The published documentation site lives at <https://ak1ra-lab.github.io/restic-profile/>, and local docs configuration is stored in `zensical.toml`.

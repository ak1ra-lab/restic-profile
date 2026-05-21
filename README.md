# restic-profile

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

Local documentation configuration lives in `zensical.toml`.

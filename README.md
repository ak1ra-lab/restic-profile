# restic-profile

Profile-based `restic` automation with a Python CLI and an Ansible role for
rendering config, deploying systemd units, and managing routine backups.

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

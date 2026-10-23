# restic-profile

**English** | [简体中文](https://github.com/ak1ra-lab/restic-profile/blob/master/README.zh-CN.md)

[![GitHub Actions Workflow Status](https://img.shields.io/github/actions/workflow/status/ak1ra-lab/restic-profile/.github%2Fworkflows%2Fpublish-to-pypi.yaml)](https://github.com/ak1ra-lab/restic-profile/actions/workflows/publish-to-pypi.yaml)
[![PyPI - Version](https://img.shields.io/pypi/v/restic-profile-cli)](https://pypi.org/project/restic-profile-cli/)
[![Docs](https://img.shields.io/badge/docs-online-0a7ea4)](https://ak1ra-lab.github.io/restic-profile/)

Profile-based [restic](https://restic.net/) wrapper, deployed with Ansible.

This repository is an Ansible collection (`ak1ra_lab.restic_profile`) plus the
`restic-profile` CLI it installs:

- **restic-profile** - reads a TOML config and runs `restic backup` / `forget` /
  `prune` with hooks and IM notifications.
- **restic_profile** role - deploys the CLI, renders the TOML config, and manages
  one systemd timer per profile (including user-level `systemd_scope: user`).
- **restic_rest_server** role - deploys a [rest-server](https://github.com/restic/rest-server)
  instance for remote backup storage.

## Install the CLI

Install the CLI on its own - Ansible, root, and systemd are not needed. `restic`
must be installed and on `PATH`:

```shell
uv tool install restic-profile-cli
restic-profile --help
```

Start from the [TOML config template][toml].

## Deploy with Ansible

```shell
git clone https://github.com/ak1ra-lab/restic-profile.git
cd restic-profile
ansible-galaxy collection install -r requirements.yaml -p ./.ansible/collections
ansible-galaxy collection install --force --collections-path .ansible/collections .
```

Pick an example from [Ansible examples][examples], fill in your `host_vars`, and
run the playbook. See [Ansible toolchain][toolchain] for the control-node setup;
building restic from source (`restic_profile_restic_install_source: go_build`)
also needs a `go` toolchain.

## Documentation

Full documentation: <https://ak1ra-lab.github.io/restic-profile/>

- [Ansible examples][examples]
- [TOML config template][toml]
- [CLI reference][cli]
- [restic-rest-server][server]
- [Ansible toolchain][toolchain]

## Development

```shell
uv sync --group dev
just lint
just typecheck
just test
```

See [AGENTS.md](https://github.com/ak1ra-lab/restic-profile/blob/master/AGENTS.md)
for the Ansible, Molecule, and documentation workflow.

[examples]: https://ak1ra-lab.github.io/restic-profile/restic-profile/examples/
[toml]: https://ak1ra-lab.github.io/restic-profile/restic-profile/toml-config/
[cli]: https://ak1ra-lab.github.io/restic-profile/restic-profile/cli/
[server]: https://ak1ra-lab.github.io/restic-profile/restic-rest-server/
[toolchain]: https://ak1ra-lab.github.io/restic-profile/ansible-toolchain/

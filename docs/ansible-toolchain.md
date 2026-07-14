# Ansible toolchain

Project-neutral notes for setting up an Ansible authoring toolchain with `uv`,
and for understanding how `ansible-lint` resolves collection paths. Copy this
page into any repository that ships an Ansible collection.

## Install the toolchain with uv

[ansible-dev-tools][adt] bundles `ansible-lint`, `ansible-navigator`, `molecule`,
`ansible-creator`, and friends behind a single `adt` entry point. The upstream
docs install it with `pip`/`pipx`; the `uv` recipe below is an equivalent that
keeps everything in one uv-managed tool environment:

```shell
uv tool install ansible-dev-tools \
  --with-executables-from ansible-builder \
  --with-executables-from ansible-core \
  --with-executables-from ansible-creator \
  --with-executables-from ansible-dev-environment \
  --with-executables-from ansible-lint \
  --with-executables-from ansible-navigator \
  --with-executables-from ansible-sign \
  --with-executables-from molecule \
  --with molecule-plugins[podman] \
  --with ansible
```

- `--with-executables-from` exposes each bundled tool's own entry point on
  `PATH` (otherwise only `adt` is linked).
- `--with ansible` adds the full `ansible` PyPI package (the batteries-included
  collection bundle) alongside `ansible-core`, so common Galaxy collections such
  as `ansible.posix` and `community.general` resolve at user level without a
  per-project copy.
- Add more runtime dependencies as needed, e.g.
  `--with boto3 --with google-auth --with proxmoxer`.

Verify with `adt --version`.

!!! note
    The `uv tool install` invocation above is **not** documented upstream - it is
    a community recipe. See [the official installation docs][adt] for the supported installers.

## Self-contained collection paths

To keep a repository's Ansible setup hermetic - never reaching into user-level or
parent directories - pin the paths in a project-local `ansible.cfg`:

```ini
[defaults]
roles_path=./roles
collections_path=./.ansible/collections
```

Install the collection's dependencies into that tree. If the playbooks reference
the collection's own roles by FQCN (`namespace.collection.*`), install the
collection itself there too:

```shell
ansible-galaxy collection install -r requirements.yaml -p ./.ansible/collections
ansible-galaxy collection install --force --collections-path .ansible/collections .
```

## Where ansible-lint installs collections

`ansible-lint` does **not** honor `collections_path` from `ansible.cfg` when it
auto-installs `requirements.yml` / `requirements.yaml`. Internally it uses
`ansible-compat`, which derives a cache directory from the **project directory**:

- Run from the project root (non-`offline` mode), it installs into
  `./.ansible/collections` - regardless of what `collections_path` says.
- `offline: true` in the ansible-lint config disables the auto-install entirely.
- If the project root is not writable, it falls back to a temporary directory.

Pinning `collections_path` to `./.ansible/collections` therefore matches
`ansible-lint`'s own behavior: linting and playbook runs share one collection
tree, and nothing leaks to the user-level `~/.ansible`.

[adt]: https://ansible.readthedocs.io/projects/dev-tools/

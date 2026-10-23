# AGENTS.md

`restic-profile` = a Python CLI (`src/restic_profile/`, tests mirror it under
`tests/`) plus Ansible roles (`roles/restic_profile`, `roles/restic_rest_server`).
See `README.md` for the deployment workflow.

## Tooling - use these, not the defaults

`just <recipe>` is a convenience wrapper for humans; each recipe is a thin
`uv run ...` (see `justfile`). Agents can call `uv run ...` directly when that is
more flexible - the two are equivalent, not mutually exclusive.

- Env/deps: **uv** (`just sync` = `uv sync --group dev`). Never `pip`/`poetry`/`pipenv`.
  The `dev` group includes the Ansible toolchain (`ansible-core`, `ansible-lint`,
  `molecule`).
- Lint+format: **ruff** (`just lint` = `uv run ruff check --fix` then
  `uv run ruff format`, over `src/ tests/ plugins/`). Never `black`/`isort`/`flake8`.
- Typecheck: **ty** (astral-sh/ty), `src/ plugins/` only
  (`just typecheck` = `uv run ty check src/ plugins/`). Never `mypy`.
- Tests: **pytest**. `just test *ARGS` = `uv run pytest -v {{ARGS}} tests/` - ARGS
  go *before* `tests/`, so `just test -k <pattern>`. Or run
  `uv run pytest -v tests/test_file.py` directly.
- Ansible lint: `just ansible-lint` (installs the collection and requirements
  first, then runs `uv run ansible-lint`).
- Molecule: `just molecule-test` / `just molecule-test-one <scenario>` /
  `just molecule-list` (see Testing below).
- Docs: `just docs-build` = `NO_MKDOCS_2_WARNING=1 uv run mkdocs build`.
- Build: `just build` = `uv build`.

Python changes MUST pass lint, typecheck, and test before commit.

## Ansible (self-contained layout)

`ansible.cfg` pins `roles_path=./roles` and `collections_path=./.ansible/collections`
so role and collection resolution never reaches user-level/parent paths. The
inventory path still includes `~/.ansible/inventory` by design. Playbooks
reference roles by FQCN (`ak1ra_lab.restic_profile.*`). Before running
`ansible-lint` or any playbook, install the dependencies into the project-local
tree:

```shell
ansible-galaxy collection install -r requirements.yaml -p ./.ansible/collections
```

- `requirements.yaml` deps: `ansible.posix`, `community.general`,
  `containers.podman`, `community.docker`, and `ak1ra_lab.general` (not on
  Galaxy, pulled from git).
- `ansible-lint` (non-`offline` mode, run from repo root) auto-installs
  `requirements.yaml` into its own cache dir `./.ansible/collections` - computed
  by ansible-compat from the project dir, ignoring `ansible.cfg`'s `collections_path`.

Ansible changes MUST pass `ansible-lint` before commit.

## Testing (Molecule)

Ansible behavior is covered by ansible-native Molecule scenarios under
`extensions/molecule/` (collection layout; the old role-level legacy scenario
has been removed).

- `config.yml` - shared config: test inventory, project-local collections path,
  `shared_state: true`, and the component test sequence.
- `default/` - the only lifecycle manager (`create` / `destroy`); it creates the
  shared systemd containers from `ghcr.io/ak1ra-lab/docker-systemd`.
- `restic_profile/basic` - system-scope backup and retention-only profiles on
  Debian 13, Ubuntu 26.04, Rocky 10, and Fedora 44.
- `restic_profile/user_scope` - user-scope timer on Debian 13, including the
  PAM/linger prerequisites for the per-user systemd manager.
- `restic_rest_server/basic` - Debian package deployment, htpasswd auth, and
  explicit test teardown.

Prerequisites: `just ansible-collection-install` and
`just ansible-requirements-install`, plus `uv` and a container runtime
(rootless Podman works; CI uses rootful Podman). The container images and
supported host matrix are documented in `extensions/molecule/inventory/`.
Role, task, or template changes SHOULD pass the relevant Molecule scenario;
run the full suite before a release. Molecule caches scenario state: after
changing a `molecule.yml`, run `uv run molecule reset` (or `molecule destroy`)
so prepare/create are re-run. A distro is eligible for the matrix only when
its image's bundled Python satisfies the project's `>=3.11` floor; drop the
distro instead of installing a newer Python next to it.

## Docs (bilingual)

`docs/` is served by mkdocs with the i18n plugin (`docs_structure: suffix`):
every page has an English `*.md` and a Simplified-Chinese `*.zh.md` sibling
(e.g. `cli.md` + `cli.zh.md`). When adding or changing user-facing behavior,
update BOTH language files.

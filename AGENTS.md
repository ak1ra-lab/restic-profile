# AGENTS.md

`restic-profile` = a Python CLI (`src/restic_profile/`, tests mirror it under
`tests/`) plus Ansible roles (`roles/restic_profile`, `roles/restic_rest_server`).
See `README.md` for the deployment workflow.

## Tooling - use these, not the defaults

`just <recipe>` is a convenience wrapper for humans; each recipe is a thin
`uv run ...` (see `justfile`). Agents can call `uv run ...` directly when that is
more flexible - the two are equivalent, not mutually exclusive.

- Env/deps: **uv** (`just sync` = `uv sync --group dev`). Never `pip`/`poetry`/`pipenv`.
- Lint+format: **ruff** (`just lint` = `uv run ruff check --fix` then
  `uv run ruff format`, over `src/ tests/ plugins/`). Never `black`/`isort`/`flake8`.
- Typecheck: **ty** (astral-sh/ty), `src/ plugins/` only
  (`just typecheck` = `uv run ty check src/ plugins/`). Never `mypy`.
- Tests: **pytest**. `just test *ARGS` = `uv run pytest -v {{ARGS}} tests/` - ARGS
  go *before* `tests/`, so `just test -k <pattern>`. Or run
  `uv run pytest -v tests/test_file.py` directly.
- Docs: `just docs-build` = `NO_MKDOCS_2_WARNING=1 uv run mkdocs build`.
- Build: `just build` = `uv build`.

Python changes MUST pass lint, typecheck, and test before commit.

## Ansible (self-contained layout)

`ansible.cfg` pins `roles_path=./roles` and `collections_path=./.ansible/collections`
and never reaches user-level/parent paths. Playbooks reference roles by FQCN
(`ak1ra_lab.restic_profile.*`). Before running `ansible-lint` or any playbook,
install the dependencies into the project-local tree:

```shell
ansible-galaxy collection install -r requirements.yaml -p ./.ansible/collections
```

- `requirements.yaml` deps: `ansible.posix`, `community.general` (usually resolve
  from user-level ansible) and `ak1ra_lab.general` (not on Galaxy, pulled from git).
- `ansible-lint` (non-`offline` mode, run from repo root) auto-installs
  `requirements.yaml` into its own cache dir `./.ansible/collections` - computed
  by ansible-compat from the project dir, ignoring `ansible.cfg`'s `collections_path`.
- Molecule scenarios under `roles/*/molecule/` are dormant - don't rely on them.

Ansible changes MUST pass `ansible-lint` before commit.

## Docs (bilingual)

`docs/` is served by mkdocs with the i18n plugin (`docs_structure: suffix`):
every page has an English `*.md` and a Simplified-Chinese `*.zh.md` sibling
(e.g. `cli.md` + `cli.zh.md`). When adding or changing user-facing behavior,
update BOTH language files.

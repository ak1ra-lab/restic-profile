# AGENTS.md

## What This Project Does

`restic-profile` bundles a Python CLI (`restic-profile`) with Ansible roles for
`restic_profile` and `restic_rest_server` deployments. See `README.md` for
setup, usage, and the development workflow.

## Environment & Tooling - CRITICAL

- Environment manager: **uv**. Sync with `uv sync --group dev`.
- Lint & format: **ruff**. Run `just lint` (or `uv run ruff check --fix src/ tests/` then `uv run ruff format src/ tests/`).
- Type check: **ty** (`astral-sh/ty`). Run `just typecheck`.
- Test runner: **pytest** (`uv run pytest -v tests/` or `just test`).
- Ansible lint: `ansible-lint` (global install, see `README.md`).
- Build: `uv build -v` (or `just build`).
- Docs: `uv run zensical build` (or `just docs-build`).

You MUST NOT use `pip`, `poetry`, `pipenv`, `mypy`, `black`, `flake8`, `isort`,
or `mkdocs` directly. All Python tooling flows through **uv** and **ruff**/**ty**.

## Conventions

### Directory Layout (mandatory for Ansible operations)

This repository MUST be cloned into the standard Ansible collection namespace
layout so that the relative `collections_path` in `ansible.cfg` resolves
correctly:

```
collections/
  ansible_collections/
    ak1ra_lab/
      restic_profile/   # <-- this repo
      general/          # ansible-collection-general
```

`ansible.cfg` sets `collections_path=../../../../collections:~/.ansible/collections`.
From `restic_profile/` this traverses up 4 levels to reach the top-level
`collections/` directory, allowing ansible to discover all collections under
that root. Any deviation from this directory structure will break collection
resolution.

### Code Layout

- Python source: `src/restic_profile/`
- Tests: `tests/restic_profile/` (mirrors source layout)
- Ansible roles: `roles/<role_name>/`
- Ansible playbooks: `playbooks/`

### Python Style

- Line length 88, double quotes, spaces for indent (see `ruff.toml`).
- Target Python 3.11+ (`pyproject.toml`).

## Testing Guidelines

- Tests live in `tests/` and mirror the `src/` package layout.
- All changes MUST pass `just lint`, `just typecheck`, and `just test` before committing.
- Run: `just test` or `uv run pytest -v tests/`.
- Coverage: `just coverage`.
- Ansible linting is separate: `ansible-lint`.
- Molecule scenarios exist under `roles/*/molecule/` but are dormant; do not
  rely on them for validation.

## Common Operations

```shell
just sync           # sync dependencies
just lint           # lint and format Python code
just typecheck      # static type check
just test           # run pytest
just build          # build distribution packages
just docs-build     # build documentation site
ansible-lint        # lint Ansible roles and playbooks
```

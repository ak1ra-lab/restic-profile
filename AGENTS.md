# AGENTS.md

`restic-profile` = a Python CLI (`src/restic_profile/`, tests mirror it under
`tests/`) plus Ansible roles (`roles/restic_profile`, `roles/restic_rest_server`).
See `README.md` for the deployment workflow.

## Tooling — use these, not the defaults

- Env/deps: **uv** (`just sync`). Never `pip`/`poetry`/`pipenv`.
- Lint+format: **ruff** over `src/ tests/ plugins/` (`just lint`). Never `black`/`isort`/`flake8`.
- Typecheck: **ty** (astral-sh/ty), `src/ plugins/` only (`just typecheck`). Never `mypy`.
- Tests: **pytest** (`just test`). Single test: `just test -k <pattern>` — ARGS are
  inserted *before* `tests/`, so pass `-k`/flags, not a bare path.
- Docs: `just docs-build` (wraps mkdocs; never call `mkdocs` directly).
- Build: `just build`. Ansible lint: `ansible-lint`.

Python changes MUST pass `just lint`, `just typecheck`, `just test` before commit.

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
  `requirements.yaml` into its own cache dir `./.ansible/collections` — computed
  by ansible-compat from the project dir, ignoring `ansible.cfg`'s `collections_path`.
- Molecule scenarios under `roles/*/molecule/` are dormant — don't rely on them.

# AGENTS.md

## What This Project Does

`restic-profile` provides the `restic-profile` Python CLI plus Ansible roles for `restic_profile` and `restic_rest_server`. The repository manages restic config rendering, backup timers, and operator workflows on managed hosts. See `README.md` for setup and user-facing usage details.

## Environment & Tooling - CRITICAL

- MUST use `uv` or `just`; treat `pyproject.toml` and `justfile` as the sources of truth.
- MUST sync dependencies with `just sync` or `uv sync --group dev`.
- MUST run tests with `just test` or `uv run pytest -v tests/<slice>` for a narrow check.
- MUST run `just lint` after Python edits and `just typecheck` after CLI or model changes.
- MUST run `ansible-lint` after changes under `roles/`, `playbooks/`, or templates.
- MUST run `just docs-build` after docs changes.
- MUST NOT use `pip install`, bare `pytest`, `ruff`, `ty`, or `zensical`.
- MUST NOT edit generated output under `site/`.
- MUST NOT treat dormant Molecule scenarios as routine validation.

## Conventions

- Python package code lives in `src/restic_profile`; tests mirror it under `tests/restic_profile`.
- Role-internal constants belong in `roles/*/vars/main.yaml`; caller-overridable values belong in `roles/*/defaults/main.yaml`.
- `roles/restic_profile/templates/etc/restic-profile/restic-profile.env.j2` is the source of truth for the shell variables managed by the selector helper.
- CLI subcommands use `argparse` plus `argcomplete` and MUST end in `set_defaults(handler=...)`.
- CLI logging is configured with `chaos_utils.logging.setup_logger`; library modules SHOULD use `logging.getLogger(__name__)`.
- YAML files MUST use the `.yaml` extension.

## Testing Guidelines

- Add or update pytest coverage when CLI behavior, config parsing, runner logic, or shipped shell helpers change.
- Mock external I/O in tests; do not make real network calls or talk to real restic backends.
- Keep tests and call sites in sync when function signatures or rendered outputs change.
- Use `ansible-lint` for roles, playbooks, and templates.
- Do NOT rely on Molecule unless the user explicitly asks for it.

## Common Operations

```shell
just sync         # install or update dev dependencies
just lint         # run ruff check and format for src/ and tests/
just typecheck    # run ty against src/
just test         # run the pytest suite
ansible-lint      # validate roles, tasks, playbooks, and templates
just docs-build   # build docs and refresh site/
```

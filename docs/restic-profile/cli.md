# restic-profile CLI reference

## Global options

```text
restic-profile COMMAND [command options]
```

`--config` is a per-command option on `backup`, `forget`, `validate`, and `list`.

## restic-profile backup PROFILE

Run `restic backup` (and optional post-backup `forget`) for one profile.

```shell
restic-profile backup myapp
restic-profile backup myapp --dry-run
restic-profile backup myapp --config /path/to/custom.toml
```

Execution order:

1. Run `prevalidate` hooks.
2. For local repositories, ensure the path exists.
3. Auto-init repository (`restic cat config` then optional `restic init`).
4. Run `before` hooks.
5. Run `restic backup --host <host> --tag <tag> ...`.
6. Optionally run `restic forget --host <host> --tag <tag> ...` when `forget=true`.
7. Run `after` hooks.
8. Run `success` hooks on success, or `failure` hooks on error.

If `prevalidate` or `before` fails, backup and `after` are skipped; only `failure`
hooks run.

`backup` requires `sources` to be non-empty. A retention-only profile (`sources: []`)
must be run through `restic-profile forget` instead.

## restic-profile forget PROFILE

Run standalone retention for one profile.

```shell
restic-profile forget prune_myapp
restic-profile forget prune_myapp --dry-run
```

Notes:

- Always filters by profile `tag`.
- Adds host filter only when `forget_current_host = true`.
- Adds `--prune` only when profile `prune = true`.
- Requires at least one non-zero `keep_*` value.

## restic-profile validate

Parse and validate TOML config.

```shell
restic-profile validate
restic-profile validate --config /etc/restic-profile/restic-profile.toml
```

Checks:

- Every profile has non-empty `repository` and `password`.
- Every retention-only profile (`sources = []`) has at least one non-zero `keep_*`.

## restic-profile list

Print profile summary.

```shell
restic-profile list
# myapp        type=backup          repository=rest:https://backup.example.com/  on_calendar=hourly
# prune_myapp  type=retention-only  repository=/srv/restic/alice/myapp           on_calendar=daily
```

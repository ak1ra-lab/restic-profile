# restic-profile CLI reference

## Global options

```text
restic-profile COMMAND [command options]
```

`--config` is a per-command option on `backup`, `retention`, `validate`, and `list`.

## restic-profile backup PROFILE

Run `restic backup` (and optional post-backup retention) for one profile.

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
6. Optionally run `restic forget --host <host> --tag <tag> ...` when `post_backup_retention=true`.
7. Run `after` hooks.
8. Run `success` hooks on success, or `failure` hooks on error.

If `prevalidate` or `before` fails, backup and `after` are skipped; only `failure`
hooks run.

`backup` requires a `backup` sub-table to be configured on the profile. A retention-only profile (one with only a `retention` sub-table configured) must be run through `restic-profile retention` instead.

## restic-profile retention PROFILE

Run standalone retention (forget & prune) for one profile.

```shell
restic-profile retention myapp
restic-profile retention myapp --dry-run
```

Notes:

- Always filters by profile `tag`.
- Adds host filter only when `forget_current_host = true` in the retention sub-table.
- Adds `--prune` only when `prune = true` in the retention sub-table.
- Requires at least one non-zero `keep_*` value in the retention sub-table.

## restic-profile validate

Parse and validate TOML config.

```shell
restic-profile validate
restic-profile validate --config /etc/restic-profile/restic-profile.toml
```

Checks:

- Every profile has a valid `repository_ref` pointing to a configured top-level repository.
- Every referenced repository has non-empty `repository` and `password`.
- Every profile has at least one of `backup` or `retention` configured.
- Every profile with a `backup` section has a non-empty `sources` list.
- Every profile with a `retention` section has at least one non-zero `keep_*` policy.

## restic-profile list

Print profile summary.

```shell
restic-profile list
# myapp        type=backup+retention  repository_ref=r1  backup_schedule=hourly  retention_schedule=daily
# prune_myapp  type=retention         repository_ref=r2  retention_schedule=daily
```

## Shell Autocompletion

`restic-profile` supports automatic tab-completion of commands and profile names via `argcomplete`.

### One-time Setup

Ensure you have `argcomplete` installed (it is installed automatically as a dependency of `restic-profile`).

#### Bash

To activate autocompletion dynamically in your current Bash session, run:

```bash
eval "$(register-python-argcomplete restic-profile)"
```

To make this persistent, append the following line to your `~/.bashrc`:

```bash
# Enable autocompletion for restic-profile
if command -v register-python-argcomplete >/dev/null 2>&1; then
    eval "$(register-python-argcomplete restic-profile)"
fi
```

#### Zsh

If you are using Zsh, you must enable `bashcompinit` compatibility first. Add the following to your `~/.zshrc`:

```zsh
# Enable bash completion compatibility
autoload -U +X bashcompinit && bashcompinit

# Enable autocompletion for restic-profile
if command -v register-python-argcomplete >/dev/null 2>&1; then
    eval "$(register-python-argcomplete restic-profile)"
fi
```

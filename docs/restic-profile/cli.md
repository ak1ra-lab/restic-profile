# restic-profile CLI reference

## Command shapes

```text
restic-profile [--config PATH] [--dry-run] PROFILE
restic-profile --check [--config PATH]
restic-profile --list [--config PATH]
```

- `PROFILE` runs the configured workflow for one profile.
- `--check` parses and validates the TOML config.
- `--list` prints a profile summary including workflow type and schedule.
- `--dry-run` only affects `PROFILE` execution; it logs commands without running them.

## restic-profile PROFILE

```shell
restic-profile myapp
restic-profile myapp --dry-run
restic-profile myapp --config /path/to/custom.toml
```

Execution depends on the profile shape:

- Backup-only profile: run `restic backup`.
- Retention-only profile: run `restic forget` and optional `--prune`.
- Backup+retention profile: run backup first, then inline retention after a successful backup.

Backup-capable profiles use this lifecycle:

1. Run `prevalidate` hooks.
2. For local repositories, ensure the path exists.
3. Auto-init repository (`restic cat config` then optional `restic init`).
4. Run `before` hooks.
5. Run `restic backup --host <host> --tag <tag> ...`.
6. If the profile also has retention config, run `restic forget --host <host> --tag <tag> ...` and optional `--prune`.
7. Run `after` hooks.
8. Run `success` hooks on success, or `failure` hooks on error.

If `prevalidate` or `before` fails, backup and `after` are skipped; only `failure`
hooks run.

Retention-only profiles skip the backup hook lifecycle and execute standalone
retention directly.

## restic-profile --check

Parse and validate TOML config.

```shell
restic-profile --check
restic-profile --check --config /etc/restic-profile/restic-profile.toml
```

Checks:

- Every profile has a valid `repository_ref` pointing to a configured top-level repository.
- Every referenced repository has non-empty `repository` and `password`.
- Every profile has at least one of `backup` or `retention` configured.
- Every profile with a `backup` section has a non-empty `sources` list.
- Every profile with a `retention` section has at least one non-zero `keep_*` policy.

## restic-profile --list

Print profile summary.

```shell
restic-profile --list
# myapp        type=backup+retention  schedule=hourly  repository=rest:https://backup.example.com/
# prune_myapp  type=retention         schedule=daily   repository=rest:https://backup.example.com/server
```

## Shell Autocompletion

`restic-profile` supports automatic tab-completion of flags and profile names via `argcomplete`.

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

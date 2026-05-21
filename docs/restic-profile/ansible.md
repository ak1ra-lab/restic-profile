# restic-profile with Ansible

If you are starting from inventory, begin with [examples.md](examples.md). This
page focuses on what the role manages and what it validates.

## Role: restic_profile

The `restic_profile` role:

1. Installs or reuses `restic` according to `restic_profile_restic_install_source`.
2. Installs `restic-profile` into `/var/lib/restic-profile/venv`.
3. Exposes `/usr/local/bin/restic-profile` as a symlink to the venv entry point for interactive use.
4. Installs `/etc/restic-profile/restic-profile-select.bash`, a sourced shell helper that defines `restic-profile-select` for interactive profile selection.
5. Renders `/etc/restic-profile/restic-profile.toml` (mode `0640`).
6. Renders one per-profile environment file and optional exclude file.
7. Deploys one systemd service+timer pair per enabled profile.

The systemd units still execute `restic_profile_bin` directly. The
`/usr/local/bin/restic-profile` symlink is only a stable operator-facing PATH
entry so you can run `restic-profile list`, `validate`, `backup`, or `forget`
without activating the dedicated virtual environment.

`/etc/restic-profile/restic-profile-select.bash` is separate from the
`restic-profile` CLI. Source it once in an interactive Bash shell to define the
`restic-profile-select` function, choose a profile by index, and then run raw
`restic` commands with the profile environment loaded into the current shell:

```shell
source /etc/restic-profile/restic-profile-select.bash
restic-profile-select
restic snapshots
restic restore latest --target /tmp/restore
```

The role intentionally does not edit per-user shell startup files such as
`~/.bashrc`. If you want the selector function available in new interactive
Bash sessions, add the sourcing snippet yourself:

```shell
test -f /etc/restic-profile/restic-profile-select.bash && source /etc/restic-profile/restic-profile-select.bash
```

The selector function sources `/etc/restic-profile/restic-profile-<name>.env`
into the current shell, so it requires the caller to have read access to that
file. With the role defaults, that usually means running it as `root`.

## Role variables

### Deployment state

| Variable                            | Default   | Description                                           |
| ----------------------------------- | --------- | ----------------------------------------------------- |
| `restic_profile_state`              | `present` | `present` deploys; `absent` removes managed resources |
| `restic_profile_pip_install_source` | `local`   | `local`, `pypi`, or `testpypi`                        |
| `restic_profile_restic_install_source` | `apt` | `apt`, `go_build`, or `existing` for the restic binary |
| `restic_profile_restic_binary`      | `""`     | Global restic executable; empty means resolve from PATH/common locations |
| `restic_profile_no_cache`           | `false`   | Global `--no-cache` toggle                            |
| `restic_profile_retry_lock`         | `""`     | Global `--retry-lock` duration; opt-in because unsupported builds fail directly |

When you configure `retry_lock`, `no_cache`, or `one_file_system`,
`restic-profile` passes those flags through unchanged. If the selected restic
binary does not support them, the restic command fails and surfaces that error
directly instead of being silently downgraded.

### Restic binary installation

`restic_profile_restic_install_source` controls how the role ensures a usable
`restic` binary is present:

- `apt`: install the distro package on the managed host.
- `go_build`: build a static binary on the control node with `roles/go_build`
	and copy it to `restic_profile_restic_install_path`.
- `existing`: skip installation and rely on an already available binary.

When you use `go_build`, the control node must have `go` in `PATH`. The role's
defaults build `https://github.com/restic/restic.git` at `master`, target
`linux/amd64`, and copy the resulting binary to `/usr/local/bin/restic`.

For one-off refreshes outside the main role flow, use
`playbooks/go_build/restic.yaml`.

### Profile dictionary

The profile schema is documented in
[profiles.md](profiles.md).

Practical deployment examples are in
[examples.md](examples.md).

Two profile fields are role-only:

- `enabled`: skip deploying the profile entirely
- `timer_enabled`: still render the units, but stop/disable the timer

### Fixed role paths

These are defined in `roles/restic_profile/vars/main.yaml` and are not intended
to be overridden.

| Variable                            | Value                                                     |
| ----------------------------------- | --------------------------------------------------------- |
| `restic_profile_config_dir`         | `/etc/restic-profile`                                     |
| `restic_profile_config_file`        | `/etc/restic-profile/restic-profile.toml`                 |
| `restic_profile_venv_dir`           | `/var/lib/restic-profile/venv`                            |
| `restic_profile_bin`                | `/var/lib/restic-profile/venv/bin/restic-profile`         |
| `restic_profile_cli_link`           | `/usr/local/bin/restic-profile`                           |
| `restic_profile_select_script_path` | `/etc/restic-profile/restic-profile-select.bash`         |
| `restic_profile_backup_unit_prefix` | `restic-profile-backup-`                                  |
| `restic_profile_forget_unit_prefix` | `restic-profile-forget-`                                  |

## Removing all managed resources

```yaml
restic_profile_state: absent
```

When `state: absent`, the role:

1. Stops and disables managed timers.
2. Removes generated service/timer units from `/etc/systemd/system`.
3. Removes `/etc/restic-profile/restic-profile.toml`.
4. Removes `/usr/local/bin/restic-profile`.
5. Removes `/etc/restic-profile/restic-profile-select.bash`.
6. Removes `/var/lib/restic-profile/venv`.

It does not remove the distro `restic` package or any go-build-managed restic
binary.

## Preflight checks

Before writing files, the role asserts that:

1. `restic_profile_restic_install_source` is one of `apt`, `go_build`, or `existing`.
1. `restic_profile_profiles` is a mapping.
2. Every enabled profile has non-empty `repository` and `password` fields.
3. Every enabled retention-only profile (`sources: []`) has at least one non-zero `keep_*` field.

## Security notes

- `/etc/restic-profile/restic-profile.toml` is mode `0640` (`root:root`).
- `/etc/restic-profile/restic-profile-<name>.env` and rendered exclude files are also mode `0640`.
- The `.env` files are rendered with shell-safe quoting so they can be sourced by `restic-profile-select` or directly in a Bash shell without expanding characters such as `$` inside secrets.
- If `system_user` is non-root, ensure that account can read the config file.
- Store secrets in Ansible Vault (`password`, `rest_password`, `aws_secret_access_key`, etc.).
- CLI credentials are passed to `restic` via environment variables only.

## Role validation

Use the Ansible toolchain documented in
[../index.md](../index.md), then run:

```shell
ansible-lint
```

The Molecule scenario under `roles/restic_profile/molecule/default/` is
currently dormant and is not part of the routine validation loop.

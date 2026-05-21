# restic-profile with Ansible

If you are starting from inventory, begin with [examples.md](examples.md). This
page focuses on what the role manages and what it validates.

## Role: restic_profile

The `restic_profile` role:

1. Installs `restic` from Debian APT.
2. Installs `restic-profile` into `/var/lib/restic-profile/venv`.
3. Renders `/etc/restic-profile/restic-profile.toml` (mode `0640`).
4. Renders one per-profile environment file and optional exclude file.
5. Deploys one systemd service+timer pair per enabled profile.

## Role variables

### Deployment state

| Variable                            | Default   | Description                                           |
| ----------------------------------- | --------- | ----------------------------------------------------- |
| `restic_profile_state`              | `present` | `present` deploys; `absent` removes managed resources |
| `restic_profile_pip_install_source` | `local`   | `local`, `pypi`, or `testpypi`                        |
| `restic_profile_restic_binary`      | `""`     | Global restic executable; empty means resolve from PATH/common locations |
| `restic_profile_no_cache`           | `false`   | Global `--no-cache` toggle                            |
| `restic_profile_retry_lock`         | `""`     | Global `--retry-lock` duration; opt-in because unsupported builds fail directly |

When you configure `retry_lock`, `no_cache`, or `one_file_system`,
`restic-profile` passes those flags through unchanged. If the selected restic
binary does not support them, the restic command fails and surfaces that error
directly instead of being silently downgraded.

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
4. Removes `/var/lib/restic-profile/venv`.

It does not remove the `restic` package.

## Preflight checks

Before writing files, the role asserts that:

1. `restic_profile_profiles` is a mapping.
2. Every enabled profile has non-empty `repository` and `password` fields.
3. Every enabled retention-only profile (`sources: []`) has at least one non-zero `keep_*` field.

## Security notes

- `/etc/restic-profile/restic-profile.toml` is mode `0640` (`root:root`).
- `/etc/restic-profile/restic-profile-<name>.env` and rendered exclude files are also mode `0640`.
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

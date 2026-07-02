# restic-profile with Ansible

If you are starting from inventory, begin with [examples.md](examples.md). This
page focuses on what the role manages and what it validates.

## Role: restic_profile

The `restic_profile` role:

1. Installs or reuses `restic` according to `restic_profile_restic_install_source`.
2. Installs `restic-profile` into `/var/lib/restic-profile/venv`.
3. Exposes `/usr/local/bin/restic-profile` as a symlink to the venv entry point for interactive use.
4. Installs `/usr/local/bin/restic-profile-scope`, a transient `systemd-run --scope` helper for manually throttled CLI runs.
5. Renders `/etc/restic-profile/restic-profile.toml` (mode `0640`).
6. Renders one repository-scoped environment file per repository actually referenced by enabled profiles, plus optional per-profile exclude files.
7. Deploys one root-run systemd service+timer pair per enabled profile.
8. Automatically stops, disables, and removes systemd units for profiles that are removed or renamed from `restic_profile_profiles`.

The systemd units still execute `restic_profile_bin` directly. The
`/usr/local/bin/restic-profile` symlink is only a stable operator-facing PATH
entry so you can run `restic-profile --list`, `restic-profile --check`, or
`restic-profile <profile>` without activating the dedicated virtual
environment.

If you want an interactive `restic-profile` run to use the same global systemd
resource controls as the managed timer services, use the separate helper:

```shell
restic-profile-scope myapp
restic-profile-scope repo-prune
```

The scope helper uses the global role defaults such as `CPUQuota=`. Per-profile
systemd overrides still apply only to the generated service units.

For raw `restic` commands, change into `/etc/restic-profile`, inspect the
rendered `.env` files, source the one you want, and then run `restic` with the
repository environment loaded into the current shell:

```shell
cd /etc/restic-profile
ls restic-profile-*.env
source ./restic-profile-r1.env
restic_cmd="${RESTIC_PROFILE_RESTIC_BINARY:-restic}"
"${restic_cmd}" snapshots
"${restic_cmd}" restore latest --target /tmp/restore
```

Current versions do not install `restic-profile-select.bash`. If an older
deployment left that helper behind, the role removes it on subsequent runs.

The role intentionally does not edit per-user shell startup files. Source the
desired `.env` file in each shell where you need direct `restic` access.

Repository `.env` files are named after `repository_ref`, for example
`/etc/restic-profile/restic-profile-r1.env`. They export repository
credentials and the global `restic_profile_restic_binary` hint when it is set;
profile-specific runtime overrides such as per-profile `restic_binary` stay in
the TOML config and generated service units.

Sourcing `/etc/restic-profile/restic-profile-<repository-ref>.env` requires the
caller to have read access to that file. With the role defaults, that usually
means running it as `root`.

## Role variables

### Deployment state

| Variable                            | Default   | Description                                           |
| ----------------------------------- | --------- | ----------------------------------------------------- |
| `restic_profile_state`              | `present` | `present` deploys; `absent` removes managed resources |
| `restic_profile_pip_install_source` | `local`   | `local`, `pypi`, or `testpypi`                        |
| `restic_profile_restic_install_source` | `apt` | `apt`, `go_build`, or `existing` for the restic binary |
| `restic_profile_restic_binary`      | `""`     | Global restic executable; empty means resolve from PATH/common locations |
| `restic_profile_systemd_cpu_quota`  | `100%`    | Global `CPUQuota=` cap for generated services and `restic-profile-scope`; set `""` to disable |
| `restic_profile_systemd_nice`       | `""`     | Global `Nice=` value for generated services and `restic-profile-scope` |
| `restic_profile_systemd_io_scheduling_class` | `""` | Global `IOSchedulingClass=` value for generated services and `restic-profile-scope` |
| `restic_profile_systemd_io_scheduling_priority` | `""` | Global `IOSchedulingPriority=` value for generated services and `restic-profile-scope` |
| `restic_profile_no_cache`           | `false`   | Global `--no-cache` toggle                            |
| `restic_profile_retry_lock`         | `""`     | Global `--retry-lock` duration; opt-in because unsupported builds fail directly |

When you configure `retry_lock`, `no_cache`, or `one_file_system`,
`restic-profile` passes those flags through unchanged. If the selected restic
binary does not support them, the restic command fails and surfaces that error
directly instead of being silently downgraded.

Systemd resource controls are applied only to the generated service units and
the `restic-profile-scope` helper. The plain `restic-profile` symlink and the
interactive selector-generated raw `restic` environment stay unmodified.

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

Role-only profile fields include:

- `enabled`: skip deploying the profile entirely; existing systemd units for this profile are automatically stopped and removed on the next run
- `timer_enabled`: still render the units, but stop/disable the timer
- `cpu_quota`: override the generated service unit's `CPUQuota=`
- `nice`: override the generated service unit's `Nice=`
- `io_scheduling_class`: override the generated service unit's `IOSchedulingClass=`
- `io_scheduling_priority`: override the generated service unit's `IOSchedulingPriority=`

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
| `restic_profile_scope_helper_path`  | `/usr/local/bin/restic-profile-scope`                     |
| `restic_profile_unit_prefix`        | `restic-profile-`                                         |

## Removing all managed resources

```yaml
restic_profile_state: absent
```

When `state: absent`, the role:

1. Stops and disables managed timers.
2. Removes generated service/timer units from `/etc/systemd/system`.
3. Removes `/etc/restic-profile/restic-profile.toml`.
4. Removes `/usr/local/bin/restic-profile`.
5. Removes `/usr/local/bin/restic-profile-scope`.
6. Removes any legacy `/etc/restic-profile/restic-profile-select.bash` left by older versions.
7. Removes `/var/lib/restic-profile/venv`.

It does not remove the distro `restic` package or any go-build-managed restic
binary.

## Cleaning up removed profiles

When you remove or rename a profile in `restic_profile_profiles`, the
role detects orphaned systemd units on disk (files whose names no longer
correspond to any enabled profile) and automatically:

1. Stops and disables orphaned `.timer` units.
2. Removes orphaned `.service` and `.timer` unit files.

This also applies when you set a previously deployed profile's `enabled`
to `false`. No separate `state: absent` step is needed; a single
`state: present` run handles the cleanup.

## Preflight checks

Before writing files, the role asserts that:

1. `restic_profile_restic_install_source` is one of `apt`, `go_build`, or `existing`.
1. `restic_profile_repositories` and `restic_profile_profiles` are mappings.
1. Every repository definition is a mapping with non-empty `repository` and `password` fields.
1. Every enabled profile is a mapping with a non-empty `repository_ref` that points to `restic_profile_repositories`.
1. Every enabled profile configures at least one of `backup` or `retention`.
1. Every enabled `backup` block is a mapping with a non-empty `sources` list.
1. Every enabled `retention` block is a mapping with at least one actionable setting: one or more non-zero `keep_*` fields and/or `prune: true`.

## Security notes

- `/etc/restic-profile/restic-profile.toml` is mode `0640` (`root:root`).
- `/etc/restic-profile/restic-profile-<repository-ref>.env` and rendered exclude files are also mode `0640`.
- Generated systemd services intentionally run as `root` because `/etc/restic-profile` contains shared config and secrets.
- The `.env` files are rendered with shell-safe quoting so they can be sourced directly in a Bash shell without expanding characters such as `$` inside secrets.
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

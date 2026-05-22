# restic_profile_profiles field map

The authoritative per-field reference lives in the inline comments in
`roles/restic_profile/defaults/main.yaml`. This page focuses on how those
fields map to rendered TOML and role behavior.

Use this with:

- [examples.md](examples.md) for scenario-based `host_vars`
- [config.md](config.md) for the TOML generated from those scenarios
- [ansible.md](ansible.md) for deployment and validation notes

## Variable shape

`restic_profile_profiles` is a dictionary keyed by profile name.

Each key becomes:

- TOML section: `[profiles.<name>]`
- systemd unit suffix:
  - `restic-profile-backup-<name>.service|timer` when `sources` is non-empty
  - `restic-profile-forget-<name>.service|timer` when `sources: []`

```yaml
restic_profile_profiles:
  myapp:
    repository: "rest:https://backup.example.com:8000/apps/myapp"
    password: "{{ vault_myapp_restic_password }}"
    sources:
      - /srv/myapp
```

## Rendered fields versus role-only fields

| Group               | Fields                                                                                              | Notes                                                                                                               |
| ------------------- | --------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------- |
| Required            | `repository`, `password`                                                                            | Required for every enabled profile                                                                                  |
| REST backend        | `rest_username`, `rest_password`, `cacert`                                                          | Rendered only when the corresponding values are set                                                                 |
| S3 backend          | `aws_default_region`, `aws_access_key_id`, `aws_secret_access_key`                                  | Rendered only when `aws_access_key_id` is set                                                                       |
| GCS backend         | `google_project_id`, `google_application_credentials`, `google_access_token`                        | Rendered only when `google_project_id` is set                                                                       |
| Backup flow         | `sources`, `tag`, `exclude_patterns`, `one_file_system`, `forget`, `forget_current_host`, `prune`   | `sources: []` makes the profile retention-only                                                                      |
| Exclude file helper | `exclude_file_content`                                                                              | Role-only input; writes `/etc/restic-profile/restic-profile-<name>.exclude` and then renders `exclude_file = ...` into TOML |
| Retention           | `keep_last`, `keep_hourly`, `keep_daily`, `keep_weekly`, `keep_monthly`, `keep_yearly`              | Retention-only profiles need at least one non-zero `keep_*`                                                         |
| Timer/runtime       | `on_calendar`, `randomized_delay_sec`, `system_user`, `restic_binary`, `no_cache`, `retry_lock` | Present in TOML and reused by the role when generating units; `restic_binary` and `no_cache` can inherit from the global setting |
| Hooks               | `hooks.shell`, `hooks.prevalidate`, `hooks.before`, `hooks.after`, `hooks.failure`, `hooks.success` | Rendered under `[profiles.<name>.hooks]`                                                                            |
| Role-only lifecycle | `enabled`, `timer_enabled`, `cpu_quota`, `nice`, `io_scheduling_class`, `io_scheduling_priority`   | Never rendered into TOML; used only when generating systemd units                                                   |

## Defaults that matter operationally

- `forget: true`: backup profiles run post-backup retention by default
- `one_file_system: false`: backups cross filesystem boundaries unless you opt in
- `forget_current_host: false`: standalone forget runs are tag-scoped, not host-scoped
- `prune: false`: standalone forget does not add `--prune` unless you opt in
- `restic_binary`: inherits `restic_profile_restic_binary`; leave it empty to use PATH-based resolution, or set an absolute path when you want an exact binary
- `cpu_quota`: inherits `restic_profile_systemd_cpu_quota`; set it to `""` on a profile to remove the generated unit's `CPUQuota=` override
- `nice`: inherits `restic_profile_systemd_nice`; leave it empty unless you want the generated unit to run below the default scheduler priority
- `io_scheduling_class` and `io_scheduling_priority`: inherit the global systemd I/O scheduling defaults and apply only to generated service units
- `no_cache`: inherits `restic_profile_no_cache` unless the profile overrides it
- `retry_lock`: inherits `restic_profile_retry_lock`; leave it empty unless the selected restic build supports `--retry-lock`
- `keep_hourly: 6`, `keep_daily: 7`, `keep_weekly: 4`, `keep_monthly: 3`: retention-only profiles are valid out of the box unless you explicitly zero all `keep_*`
- `enabled: true`, `timer_enabled: true`: profiles deploy and their timers start unless you disable them

## Hook lifecycle

All hook commands run as `hooks.shell -c <command>`.

1. `prevalidate`
2. Repository/location checks and optional auto-init
3. `before`
4. Backup and optional post-backup forget
5. `after`
6. `success` or `failure`

If `prevalidate` or `before` fails, backup and `after` are skipped and only
`failure` hooks run.

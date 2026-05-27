# restic_profile_profiles field map

The authoritative per-field reference lives in the inline comments in
`roles/restic_profile/defaults/main.yaml`. This page focuses on how those
fields map to rendered TOML and role behavior.

Use this with:

- [examples.md](examples.md) for scenario-based `host_vars`
- [config.md](config.md) for the TOML generated from those scenarios
- [ansible.md](ansible.md) for deployment and validation notes

## Variable shape

`restic_profile_repositories` is a dictionary keyed by repository reference name.
`restic_profile_profiles` is a dictionary keyed by profile name.

Each profile key becomes:

- TOML section: `[profiles.<name>]`
- systemd units:
  - `restic-profile-backup-<name>.service|timer` when `backup` sub-table is configured
  - `restic-profile-retention-<name>.service|timer` when `retention` is configured for a standalone retention run, meaning the profile is retention-only or `backup.post_backup_retention` is not enabled

```yaml
restic_profile_repositories:
  r1:
    repository: "rest:https://backup.example.com:8000/apps/myapp"
    password: "{{ vault_myapp_restic_password }}"

restic_profile_profiles:
  myapp:
    repository_ref: r1
    backup:
      sources:
        - /srv/myapp
```

## Rendered fields versus role-only fields

| Group | Fields | Notes |
| --- | --- | --- |
| Required | `repository_ref` | Required for every enabled profile; resolves credentials from `restic_profile_repositories` |
| Repository config | `repository`, `password`, `rest_username`, `rest_password`, `cacert`, `aws_default_region`, `aws_access_key_id`, `aws_secret_access_key`, `google_project_id`, `google_application_credentials`, `google_access_token` | Defined under `restic_profile_repositories` keys |
| Backup sub-table | `sources`, `exclude_patterns`, `one_file_system`, `post_backup_retention`, `on_calendar`, `randomized_delay_sec` | Inside profile `backup` block. Timer units generated only if `on_calendar` is non-empty |
| Exclude file helper | `exclude_file_content` | Role-only input inside `backup` block; writes `/etc/restic-profile/restic-profile-<name>.exclude` and then renders `exclude_file = ...` into TOML |
| Retention sub-table | `keep_last`, `keep_hourly`, `keep_daily`, `keep_weekly`, `keep_monthly`, `keep_yearly`, `prune`, `forget_current_host`, `on_calendar`, `randomized_delay_sec` | Inside profile `retention` block. Standalone retention units are rendered only when `backup.post_backup_retention` is disabled or no backup block exists; timer units are generated only if `on_calendar` is non-empty |
| Profile level runtime | `tag`, `system_user`, `restic_binary`, `no_cache`, `retry_lock` | Profile-level overrides; `restic_binary` and `no_cache` can inherit from global settings |
| Hooks | `hooks.shell`, `hooks.prevalidate`, `hooks.before`, `hooks.after`, `hooks.failure`, `hooks.success` | Rendered under `[profiles.<name>.hooks]` |
| Hook file helpers | `hooks.<phase>_scripts`, `hooks.<phase>_templates` | Role-only inputs; copy or render controller-side files to `/etc/restic-profile/hooks.d/restic-profile-<name>.<phase>-<seq>.sh` and append those paths to `hooks.<phase>` |
| Role-only lifecycle | `enabled`, `timer_enabled`, `cpu_quota`, `nice`, `io_scheduling_class`, `io_scheduling_priority` | Never rendered into TOML; used only when generating systemd units |

## Defaults that matter operationally

- `post_backup_retention: false`: backup runs do not run post-backup retention by default unless you explicitly opt in
- `post_backup_retention: true`: backup runs invoke retention inline after a successful backup, so the role does not render a separate standalone retention unit for that same profile
- `one_file_system: false`: backups cross filesystem boundaries unless you opt in
- `forget_current_host: false`: standalone retention runs are tag-scoped, not host-scoped
- `prune: false`: standalone retention does not add `--prune` unless you opt in
- `restic_binary`: inherits `restic_profile_restic_binary`; leave it empty to use PATH-based resolution, or set an absolute path when you want an exact binary
- `cpu_quota`: inherits `restic_profile_systemd_cpu_quota`; set it to `""` on a profile to remove the generated unit's `CPUQuota=` override
- `nice`: inherits `restic_profile_systemd_nice`; leave it empty unless you want the generated unit to run below the default scheduler priority
- `io_scheduling_class` and `io_scheduling_priority`: inherit the global systemd I/O scheduling defaults and apply only to generated service units
- `no_cache`: inherits `restic_profile_no_cache` unless the profile overrides it
- `retry_lock`: inherits `restic_profile_retry_lock`; leave it empty unless the selected restic build supports `--retry-lock`
- `enabled: true`, `timer_enabled: true`: profiles deploy and their timers start unless you disable them

## Hook lifecycle

All hook commands run as `hooks.shell -c <command>`.

When you use `hooks.<phase>_scripts` or `hooks.<phase>_templates`, the role
manages executable files under `/etc/restic-profile/hooks.d/` and appends those
paths to the matching `hooks.<phase>` array in TOML. Within a phase, the order is:

1. Inline `hooks.<phase>` commands
2. Copied `hooks.<phase>_scripts`
3. Rendered `hooks.<phase>_templates`

1. `prevalidate`
2. Repository/location checks and optional auto-init
3. `before`
4. Backup and optional post-backup retention
5. `after`
6. `success` or `failure`

If `prevalidate` or `before` fails, backup and `after` are skipped and only
`failure` hooks run.

Hook templates render with these extra variables in scope:

- `restic_profile_hook_profile_name`: the current profile name
- `restic_profile_hook_profile`: the current profile data structure
- `restic_profile_hook_phase`: the lifecycle phase being rendered
- `restic_profile_hook_index`: the 1-based sequence number for the rendered template file within that phase
- `restic_profile_hook_dest_path`: the final remote path under `/etc/restic-profile/hooks.d/`

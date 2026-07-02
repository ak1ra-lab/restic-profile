# restic-profile configuration

`restic-profile` reads one TOML file (default: `/etc/restic-profile/restic-profile.toml`).
Use `--config` to override the path.

If you are deploying with the Ansible role, start from [examples.md](examples.md).
That page shows the `host_vars` you author. This page shows the rendered TOML that
the CLI consumes.

This page is intentionally example-first rather than a field-by-field reference.
For the Ansible-side field lookup, see [profiles.md](profiles.md).

## Generated shape

```toml
[global]
restic_binary = ""
no_cache = false
retry_lock = ""
unlock = false
```

Credentials and URLs are defined under a top-level `[repositories]` section to keep them DRY and independent of backup/retention operations. Each profile in `[profiles.<name>]` references its repository using the `repository_ref` key.

Backup and retention data stay grouped in nested sub-tables, but schedule now
lives at the profile root:
- `[profiles.<name>]`: common runtime fields plus the single profile schedule.
- `[profiles.<name>.backup]`: sources, exclusions, and backup-only flags.
- `[profiles.<name>.retention]`: retention actions (`keep_*`, `prune`), plus host scoping for forget.

Two role-only controls never appear in the TOML:

- `enabled`: skip deployment entirely when `false`
- `timer_enabled`: deploy units but stop/disable the timer when `false`

The Ansible role's systemd resource controls (`cpu_quota`, `nice`,
`io_scheduling_class`, `io_scheduling_priority`) also stay outside the TOML.
They are applied only when rendering the generated service units and the
optional `restic-profile-scope` helper.

`exclude_file_content` is also Ansible-only input: the role writes a separate
exclude file and then renders its path into `exclude_file` inside the profile's backup sub-table.

`hooks.<phase>_scripts` and `hooks.<phase>_templates` are likewise Ansible-only
inputs. The role copies or renders them to
`/etc/restic-profile/hooks.d/restic-profile-<name>.<phase>-<seq>.sh` and then
appends those paths to the matching `hooks.<phase>` array in TOML.

When you deploy through the Ansible role, generated systemd services always run
as `root` so they can read the shared config and secrets under
`/etc/restic-profile`. Per-profile `system_user` is no longer part of the
runtime model, and the role does not render it into the generated TOML.

Additional runtime fields worth knowing:

- `restic_binary`: optional global or per-profile string; when empty, `restic-profile` resolves `restic` from PATH to an absolute path and then falls back to common locations such as `/usr/local/bin/restic` and `/usr/bin/restic`
- `no_cache`: optional global or per-profile boolean that adds `--no-cache`; profiles inherit the global value unless they set their own override
- `on_calendar` / `randomized_delay_sec`: optional per-profile schedule for the single generated timer
- `one_file_system`: optional per-profile backup boolean that adds `--one-file-system` to `restic backup`
- `forget_current_host`: defaults to `true` for retention blocks; set it to `false` only when one retention job should manage snapshots created by other hosts
- `retention`: a retention block is actionable when at least one `keep_*` value is non-zero or `prune = true`; prune-only profiles run standalone `restic prune`
- Unsupported configured flags are not masked by `restic-profile`; the selected restic binary fails directly so operators can either upgrade restic, clear the flag, or pin `restic_binary` to a newer build
- Missing `sources` paths are warned about and skipped at runtime; if no configured source still exists, `restic-profile <profile>` aborts before invoking `restic`

## Rendered TOML: REST backup client

This is the TOML rendered from the first scenario in [examples.md](examples.md).

```toml
[global]
restic_binary = "/usr/local/bin/restic"
no_cache = false
retry_lock = "10m"

[repositories.r1]
repository = "rest:https://backup.example.com:8000/alice/home-alice"
password = "vault-redacted"
rest_username = "alice"
rest_password = "vault-redacted"
cacert = "/etc/ssl/certs/backup-ca.pem"

[profiles.home-alice]
repository_ref = "r1"
tag = "home-alice"
on_calendar = "hourly"
randomized_delay_sec = "15min"
restic_binary = "/usr/local/bin/restic"
retry_lock = "20m"

[profiles.home-alice.backup]
sources = [
	"/home/alice",
]
exclude_patterns = [
	"*.bak",
	"*.tmp",
]
exclude_file = "/etc/restic-profile/restic-profile-home-alice.exclude"
one_file_system = true

[profiles.home-alice.retention]
keep_last = 0
keep_hourly = 24
keep_daily = 14
keep_weekly = 8
keep_monthly = 12
keep_yearly = 0

[profiles.home-alice.hooks]
shell = "/bin/bash"
prevalidate = [
	"mountpoint -q /home/alice",
]
before = [
	"systemctl stop myapp.service",
]
after = [
	"systemctl start myapp.service",
]
failure = [
	"logger -t restic-profile 'home-alice backup failed'",
]
success = [
	"logger -t restic-profile 'home-alice backup succeeded'",
	"/etc/restic-profile/hooks.d/restic-profile-home-alice.success-01.sh",
]
```

If a phase mixes inline commands with file-backed hooks, TOML order stays stable:
inline `hooks.<phase>` entries first, then `hooks.<phase>_scripts`, then
`hooks.<phase>_templates`.

## Per-profile Systemd Timers and Services

| Profile shape | Generated units | Invocation |
| --- | --- | --- |
| `backup` only | `restic-profile-<name>.{service,timer}` | `restic-profile <name>` |
| `retention` only | `restic-profile-<name>.{service,timer}` | `restic-profile <name>` |
| `backup` + `retention` | `restic-profile-<name>.{service,timer}` | `restic-profile <name>` |

Timer units are deployed only when the profile-level `on_calendar` is non-empty.
Mixed profiles always run inline retention after a successful backup.

## Rendered TOML: retention-only repository host

```toml
[global]
restic_binary = ""
no_cache = false
retry_lock = ""

[repositories.r1]
repository = "/srv/restic/apps/myapp"
password = "vault-redacted"

[profiles.myapp_retention]
repository_ref = "r1"
tag = "myapp"
on_calendar = "daily"
randomized_delay_sec = "30min"
retry_lock = ""

[profiles.myapp_retention.retention]
keep_last = 0
keep_hourly = 0
keep_daily = 14
keep_weekly = 8
keep_monthly = 12
keep_yearly = 0
prune = true
forget_current_host = false
```

Use this pattern when backup clients write to an append-only REST repository and
you want retention plus `--prune` to run only on the repository host.

## Rendered TOML: S3-compatible backend

```toml
[global]
restic_binary = ""
no_cache = false
retry_lock = ""

[repositories.s3_db]
repository = "s3:https://s3.example.com/backups/postgresql"
password = "vault-redacted"
aws_default_region = "us-east-1"
aws_access_key_id = "vault-redacted"
aws_secret_access_key = "vault-redacted"

[profiles.postgres-basebackup]
repository_ref = "s3_db"
tag = "postgres-basebackup"
on_calendar = "03:15"
randomized_delay_sec = "5min"
retry_lock = ""

[profiles.postgres-basebackup.backup]
sources = [
	"/var/backups/postgresql",
]
exclude_patterns = [
	"*.partial",
]

[profiles.postgres-basebackup.retention]
keep_last = 7
keep_hourly = 0
keep_daily = 7
keep_weekly = 4
keep_monthly = 3
keep_yearly = 0
```

## Rendered TOML: GCS with ADC or explicit credentials

```toml
[global]
restic_binary = ""
no_cache = false
retry_lock = ""

[repositories.gcs_analytics]
repository = "gs:my-bucket:/analytics"
password = "vault-redacted"
google_project_id = "company-prod"
google_application_credentials = ""
google_access_token = ""

[profiles.analytics]
repository_ref = "gcs_analytics"
tag = "analytics"
on_calendar = "daily"
retry_lock = ""

[profiles.analytics.backup]
sources = [
	"/srv/analytics",
]

[profiles.analytics.retention]
keep_last = 0
keep_hourly = 0
keep_daily = 7
keep_weekly = 4
keep_monthly = 6
keep_yearly = 0
```

For GCS, set `google_project_id` and then choose one of these auth modes:

- Application Default Credentials: leave both `google_application_credentials` and `google_access_token` empty
- Service-account file: set `google_application_credentials`
- Short-lived OAuth2 token: set `google_access_token` (takes precedence over the file)

For S3-compatible storage, the custom endpoint lives in the `repository` URL
itself, for example `s3:https://server:port/bucket-name`. Set
`aws_default_region` only when that backend requires an explicit region that
cannot be inferred from the repository URL.

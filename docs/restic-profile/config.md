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
```

Each `[profiles.<name>]` block is one profile. The CLI reads the TOML fields;
the role additionally uses `sources`, `on_calendar`, and `randomized_delay_sec`
to decide which systemd units to render.

Two role-only controls never appear in the TOML:

- `enabled`: skip deployment entirely when `false`
- `timer_enabled`: deploy units but stop/disable the timer when `false`

The Ansible role's systemd resource controls (`cpu_quota`, `nice`,
`io_scheduling_class`, `io_scheduling_priority`) also stay outside the TOML.
They are applied only when rendering the generated service units and the
optional `restic-profile-scope` helper.

`exclude_file_content` is also Ansible-only input: the role writes a separate
exclude file and then renders its path into `exclude_file`.

Additional runtime fields worth knowing:

- `restic_binary`: optional global or per-profile string; when empty, `restic-profile` resolves `restic` from PATH to an absolute path and then falls back to common locations such as `/usr/local/bin/restic` and `/usr/bin/restic`
- `no_cache`: optional global or per-profile boolean that adds `--no-cache`; profiles inherit the global value unless they set their own override
- `one_file_system`: optional per-profile boolean that adds `--one-file-system` to `restic backup`
- Unsupported configured flags are not masked by `restic-profile`; the selected restic binary fails directly so operators can either upgrade restic, clear the flag, or pin `restic_binary` to a newer build
- Missing `sources` paths are warned about and skipped at runtime; if no configured source still exists, `restic-profile backup` aborts before invoking `restic`

## Rendered TOML: REST backup client

This is the TOML rendered from the first scenario in [examples.md](examples.md).

```toml
[global]
restic_binary = "/usr/local/bin/restic"
no_cache = false
retry_lock = "10m"

[profiles.home-alice]
# Repository and REST backend credentials.
repository = "rest:https://backup.example.com:8000/alice/home-alice"
password = "vault-redacted"
rest_username = "alice"
rest_password = "vault-redacted"
cacert = "/etc/ssl/certs/backup-ca.pem"

# Backup input.
sources = [
	"/home/alice",
]
tag = "home-alice"
exclude_patterns = [
	"*.bak",
	"*.tmp",
]
exclude_file = "/etc/restic-profile/restic-profile-home-alice.exclude"

# Post-backup retention runs after each backup.
one_file_system = true
forget = true
forget_current_host = false
prune = false

# Retention policy.
keep_last = 0
keep_hourly = 24
keep_daily = 14
keep_weekly = 8
keep_monthly = 12
keep_yearly = 0

# Timer/runtime fields are still present in TOML because the role and CLI share
# the same profile object.
on_calendar = "hourly"
randomized_delay_sec = "15min"
system_user = "root"
restic_binary = "/usr/local/bin/restic"
retry_lock = "20m"

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
]
```

## Rendered TOML: retention-only repository host

| Condition           | Profile type   | Generated units                                | Invocation                     |
| ------------------- | -------------- | ---------------------------------------------- | ------------------------------ |
| `sources` non-empty | backup         | `restic-profile-backup-<name>.{service,timer}` | `restic-profile backup <name>` |
| `sources = []`      | retention-only | `restic-profile-forget-<name>.{service,timer}` | `restic-profile forget <name>` |

```toml
[global]
restic_binary = ""
no_cache = false
retry_lock = ""

[profiles.myapp_retention]
# Retention-only profile on the repository host.
repository = "/srv/restic/apps/myapp"
password = "vault-redacted"
sources = []
tag = "myapp"
exclude_patterns = []
forget = true
forget_current_host = false
prune = true

keep_last = 0
keep_hourly = 0
keep_daily = 14
keep_weekly = 8
keep_monthly = 12
keep_yearly = 0

on_calendar = "daily"
randomized_delay_sec = "30min"
system_user = "restic-rest-server"
retry_lock = ""
```

Use this pattern when backup clients write to an append-only REST repository and
you want retention plus `--prune` to run only on the repository host.

## Rendered TOML: S3-compatible backend

```toml
[global]
restic_binary = ""
no_cache = false
retry_lock = ""

[profiles.postgres-basebackup]
repository = "s3:https://s3.example.com/backups/postgresql"
password = "vault-redacted"
aws_default_region = "us-east-1"
aws_access_key_id = "vault-redacted"
aws_secret_access_key = "vault-redacted"

sources = [
	"/var/backups/postgresql",
]
tag = "postgres-basebackup"
exclude_patterns = [
	"*.partial",
]
forget = true
forget_current_host = false
prune = false

keep_last = 7
keep_hourly = 0
keep_daily = 7
keep_weekly = 4
keep_monthly = 3
keep_yearly = 0

on_calendar = "03:15"
randomized_delay_sec = "5min"
system_user = "root"
retry_lock = ""
```

## Rendered TOML: GCS with ADC or explicit credentials

```toml
[global]
restic_binary = ""
no_cache = false
retry_lock = ""

[profiles.analytics]
repository = "gs:my-bucket:/analytics"
password = "vault-redacted"
google_project_id = "company-prod"
google_application_credentials = ""
google_access_token = ""

sources = [
	"/srv/analytics",
]
tag = "analytics"
exclude_patterns = []
forget = true
forget_current_host = false
prune = false

keep_last = 0
keep_hourly = 0
keep_daily = 7
keep_weekly = 4
keep_monthly = 6
keep_yearly = 0

on_calendar = "daily"
randomized_delay_sec = "10min"
system_user = "root"
retry_lock = ""
```

For GCS, set `google_project_id` and then choose one of these auth modes:

- Application Default Credentials: leave both `google_application_credentials` and `google_access_token` empty
- Service-account file: set `google_application_credentials`
- Short-lived OAuth2 token: set `google_access_token` (takes precedence over the file)

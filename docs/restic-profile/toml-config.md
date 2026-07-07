```toml
# restic-profile.toml — well-commented starting config
#
# Copy this file to /etc/restic-profile/restic-profile.toml, fill in your
# credentials and paths, then run:
#   restic-profile --check           # validate the config
#   restic-profile --list            # list all profiles
#   restic-profile <profile>         # run a profile
#   restic-profile <profile> -n      # dry-run (log commands, no execution)
#
# Every field shown at its default value. Delete any section you don't need.

# ---- Global defaults ----
# Profiles inherit these unless they set their own override.
[global]
restic_binary = ""       # empty = resolve `restic` from PATH
no_cache = false         # add --no-cache to every invocation
retry_lock = ""          # --retry-lock duration, e.g. "10m"
                         # Leave empty on restic ≤ 0.14 (unsupported).
unlock = false           # run `restic unlock` before every workflow
template_dir = ""        # directory with custom notify_*.md.j2 templates;
                         # leave empty to use built-in defaults

# ---- Repositories ----
# Pick ONE backend per repository. Delete the examples you don't need.

# Local filesystem
[repositories.local]
repository = "/srv/restic/myhost"
password = "replace-me-with-a-strong-password"

# REST server (append-only capable, multi-client friendly)
[repositories.rest]
repository = "rest:https://backup.example.com:8000/user/hostname"
password = "replace-me"
rest_username = "alice"
rest_password = "replace-me"
cacert = ""              # optional: path to CA cert for self-signed TLS

# S3-compatible (MinIO, Ceph, AWS S3, etc.)
# The endpoint lives directly in the repository URL:
#   s3:https://s3.example.com/bucket-name
[repositories.s3]
repository = "s3:https://s3.example.com/backups/myhost"
password = "replace-me"
aws_default_region = ""                  # optional; set only when needed
aws_access_key_id = "AKIAIOSFODNN7EXAMPLE"
aws_secret_access_key = "replace-me"

# Google Cloud Storage
[repositories.gcs]
repository = "gs:my-bucket:/prefix"
password = "replace-me"
google_project_id = "my-gcp-project"
google_application_credentials = ""      # path to service-account JSON key
                                         # leave both empty for ADC on GCE/GKE
google_access_token = ""                 # short-lived OAuth2 token;
                                         # takes precedence over the key file

# Per-repository runtime env vars (injected at subprocess level, never persisted)
# [repositories.rest.env]
# HTTP_PROXY = "http://proxy:8080"
# RESTIC_COMPRESSION = "max"
# RESTIC_PACK_SIZE = "64"

# ---- Notifications (optional) ----
# Supported: telegram, dingtalk, wechat.

[notify.telegram]
type = "telegram"
token = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
chat_id = -1001234567890
timeout = 5.0           # seconds; min 0.1
top_files_limit = 3     # max files shown in success notification; 0 = disable

[notify.dingtalk]
type = "dingtalk"
access_token = "replace-me"
secret = ""             # optional: secret for HMAC-SHA256 signing

[notify.wechat]
type = "wechat"
key = "replace-me"      # webhook key from WeChat Work bot

# Optional: HTTP proxy for notification calls only (never affects restic)
# [notify.telegram.env]
# HTTPS_PROXY = "http://proxy:8080"

# ---- Profiles ----
# Each profile maps to one systemd timer+service pair when deployed via Ansible.
# profile_name becomes: [profiles.profile_name] and restic-profile-profile_name.{service,timer}
# At least one of [profiles.<name>.backup] OR [profiles.<name>.retention] is required.

# --- Example A: backup only ---
[profiles.home]
repository_ref = "rest"         # must match a key in [repositories]
notify_ref = ""                 # reference a [notify.*] channel, e.g. "telegram"
tag = "home"                    # snapshot tag; defaults to profile name
on_calendar = "hourly"          # systemd OnCalendar=; empty disables the timer
randomized_delay_sec = "15min"  # systemd RandomizedDelaySec=

# Per-profile overrides (inherit from [global] when unset):
restic_binary = ""              # empty = use global
no_cache = false                # override global --no-cache
retry_lock = ""                 # override global --retry-lock
unlock = false                  # override global unlock

# Optional: profile-level runtime env vars (injected after repository env;
# useful for hook credentials: PGPASSWORD, MYSQL_PWD, etc.)
# [profiles.home.env]
# PGPASSWORD = "..."
# MYSQL_PWD = "..."

[profiles.home.hooks]
shell = "/bin/sh"               # each command runs as: shell -c <command>
prevalidate = [
    # "mountpoint -q /home/alice",
]
before = [
    # "systemctl stop some-service.service",
]
after = [
    # "systemctl start some-service.service",
]
failure = [
    # "logger -t restic-profile 'home backup failed'",
]
success = [
    # "logger -t restic-profile 'home backup succeeded'",
    # "/etc/restic-profile/hooks.d/my-success-script.sh",
]

[profiles.home.backup]
sources = [
    "/home/alice",
    "/home/alice/Documents",
]
exclude_patterns = [
    "*.tmp",
    ".cache/",
]
exclude_file = ""               # path to an --exclude-file (one pattern per line)
one_file_system = false         # add --one-file-system to restic backup

# --- Example B: backup + inline retention ---
[profiles.server]
repository_ref = "rest"
notify_ref = "telegram"
on_calendar = "daily"
randomized_delay_sec = "30min"

[profiles.server.hooks]
shell = "/bin/bash"
before = ["systemctl stop myapp.service"]
after = ["systemctl start myapp.service"]

[profiles.server.backup]
sources = ["/srv/myapp", "/etc/myapp"]
exclude_patterns = ["*.log", "*.partial"]

[profiles.server.retention]
keep_last = 0
keep_hourly = 24
keep_daily = 14
keep_weekly = 8
keep_monthly = 12
keep_yearly = 0
prune = false               # add --prune to `restic forget`
forget_current_host = true  # hard-coded to true for inline retention;
                            # only used by standalone retention profiles

# --- Example C: standalone retention (no backup block) ---
# Use this on the repository host when backup clients write to a shared repo.
[profiles.prune-demo]
repository_ref = "local"
tag = "myapp"                   # match the tag used by backup clients
on_calendar = "daily"
randomized_delay_sec = "30min"

[profiles.prune-demo.retention]
keep_last = 0
keep_hourly = 0
keep_daily = 14
keep_weekly = 8
keep_monthly = 12
keep_yearly = 0
prune = true                    # run restic prune after forget
forget_current_host = false     # manage snapshots from ALL hosts
```

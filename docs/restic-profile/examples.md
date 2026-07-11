# Ansible host_vars examples

All examples are `host_vars` snippets for the `restic_profile` role.
Every field defaults to a sensible value — see
`roles/restic_profile/defaults/main.yaml` for the full reference and inline
comments.

```yaml
# playbooks/restic-profile.yaml
---
- name: manage restic backup profiles
  hosts: "{{ playbook_hosts | default('restic_profile_nodes') }}"
  gather_facts: false
  become: true
  tasks:
    - name: apply restic_profile role
      ansible.builtin.import_role:
        name: ak1ra_lab.restic_profile.restic_profile
```

---

## 1. Minimal backup to a REST server

```yaml
restic_profile_repositories:
  r1:
    repository: "rest:https://backup.example.com:8000/alice/laptop"
    password: "{{ vault_laptop_restic_password }}"
    rest_username: "alice"
    rest_password: "{{ vault_rest_server_alice_password }}"

restic_profile_profiles:
  laptop-home:
    repository_ref: r1
    on_calendar: "hourly"
    randomized_delay_sec: "15min"
    backup:
      sources:
        - /home/alice
```

One profile, one timer, no retention. `tag` defaults to the profile name `laptop-home`.

---

## 2. Backup + retention + Telegram notification + hooks

```yaml
restic_profile_notify_configs:
  tg:
    type: telegram
    token: "{{ vault_telegram_bot_token }}"
    chat_id: -1001234567890
    env:
      HTTPS_PROXY: "http://proxy.example.com:8080"
      NO_PROXY: "localhost,127.0.0.1,.local"

restic_profile_repositories:
  r1:
    repository: "rest:https://backup.example.com:8000/apps/myapp"
    password: "{{ vault_myapp_restic_password }}"
    rest_username: "myapp"
    rest_password: "{{ vault_rest_server_myapp_password }}"

restic_profile_profiles:
  myapp:
    repository_ref: r1
    notify_ref: tg
    on_calendar: "daily"
    randomized_delay_sec: "30min"
    hooks:
      prevalidate:
        - "test -d /srv/myapp || exit 1"
      before:
        - "systemctl stop myapp.service"
      after:
        - "systemctl start myapp.service"
    backup:
      sources:
        - /srv/myapp
        - /etc/myapp
      exclude_patterns:
        - "*.tmp"
        - ".venv/"
      exclude_file_content: |
        __pycache__/
        node_modules/
    retention:
      keep_daily: 14
      keep_weekly: 8
      keep_monthly: 12
```

Backup runs first, then inline retention (host-scoped). On success, Telegram gets
snapshot stats and top-N largest files.

Set `enabled: false` on a profile to stop and remove its units on the next run.
Set `timer_enabled: false` to deploy units but keep the timer stopped.

---

## 3. Retention-only on the repository host

```yaml
restic_profile_repositories:
  r1:
    repository: "/srv/restic/apps/myapp"
    password: "{{ vault_myapp_restic_password }}"

restic_profile_profiles:
  myapp-retention:
    repository_ref: r1
    tag: "myapp"
    on_calendar: "daily"
    retention:
      forget_current_host: false
      prune: true
      keep_daily: 14
      keep_weekly: 8
      keep_monthly: 12
```

No `backup` block — this is a pure retention profile. `forget_current_host: false`
lets it manage snapshots from multiple backup clients sharing the same tag.

---

## 4. S3-compatible backend with PostgreSQL

```yaml
restic_profile_repositories:
  s3:
    repository: "s3:https://s3.example.com/backups/postgresql"
    password: "{{ vault_postgres_restic_password }}"
    aws_default_region: "us-east-1"
    aws_access_key_id: "{{ vault_s3_access_key }}"
    aws_secret_access_key: "{{ vault_s3_secret_key }}"

restic_profile_profiles:
  postgres:
    repository_ref: s3
    on_calendar: "03:15"
    randomized_delay_sec: "5min"
    env:
      PGHOST: "{{ vault_postgres_host }}"
      PGPORT: "{{ vault_postgres_port | default('5432') }}"
      PGUSER: "{{ vault_postgres_user }}"
      PGPASSWORD: "{{ vault_postgres_password }}"
    hooks:
      before:
        - "mkdir -p /var/backups/postgresql"
        - "pg_dumpall -U postgres > /var/backups/postgresql/all.sql"
      success:
        - "rm -f /var/backups/postgresql/all.sql"
    backup:
      sources:
        - /var/backups/postgresql
    retention:
      keep_last: 7
      keep_daily: 7
      keep_weekly: 4
```

The S3 endpoint is embedded in the `repository` URL (`s3:https://host/bucket`).
For GCS, use `gs:bucket-name:/prefix` and set `google_project_id`.

Use `pg_dumpall` for a full cluster dump (roles + all databases) or
`pg_dump <dbname>` to export individual databases. Never back up PostgreSQL
data directories directly.

---

## 5. MySQL backup

```yaml
restic_profile_repositories:
  r1:
    repository: "rest:https://backup.example.com:8000/apps/mysql"
    password: "{{ vault_mysql_restic_password }}"
    rest_username: "mysql"
    rest_password: "{{ vault_rest_server_mysql_password }}"

restic_profile_profiles:
  mysql:
    repository_ref: r1
    on_calendar: "daily"
    randomized_delay_sec: "10min"
    env:
      MYSQL_HOST: "{{ vault_mysql_host }}"
      MYSQL_TCP_PORT: "{{ vault_mysql_port | default('3306') }}"
      MYSQL_PWD: "{{ vault_mysql_root_password }}"
    hooks:
      before:
        - "mkdir -p /var/backups/mysql"
        - "mysqldump --all-databases --single-transaction -u root > /var/backups/mysql/all.sql"
      success:
        - "rm -f /var/backups/mysql/all.sql"
    backup:
      sources:
        - /var/backups/mysql
    retention:
      keep_daily: 7
```

`--single-transaction` ensures a consistent snapshot for InnoDB tables without
blocking writes. Use `--lock-tables` for MyISAM. Never back up
`/var/lib/mysql` directly.

---

## 6. SQLite backup

```yaml
restic_profile_repositories:
  r1:
    repository: "/srv/restic/apps/sqlite"
    password: "{{ vault_sqlite_restic_password }}"

restic_profile_profiles:
  sqlite:
    repository_ref: r1
    on_calendar: "daily"
    hooks:
      before:
        - "mkdir -p /var/backups/sqlite"
        - "sqlite3 /srv/myapp/data.db '.backup /var/backups/sqlite/data.db'"
      success:
        - "rm -f /var/backups/sqlite/data.db"
    backup:
      sources:
        - /var/backups/sqlite
    retention:
      keep_daily: 7
```

SQLite's `.backup` command creates a consistent snapshot using the online
backup API. Avoid copying the database file directly while it's in use.

---

## 7. GitLab backups

```yaml
restic_profile_repositories:
  r1:
    repository: "rest:https://backup.example.com:8000/apps/gitlab"
    password: "{{ vault_gitlab_restic_password }}"

restic_profile_profiles:
  gitlab:
    repository_ref: r1
    on_calendar: "daily"
    randomized_delay_sec: "15min"
    hooks:
      before:
        - "/usr/bin/gitlab-rake gitlab:backup:create"
    backup:
      sources:
        - /var/opt/gitlab/backups
    retention:
      keep_daily: 7
      keep_weekly: 4
```

`gitlab:backup:create` writes timestamped tarballs to
`/var/opt/gitlab/backups`. GitLab's built-in
`gitlab_rails['backup_keep_time']` (default `604800` — 7 days in
`/etc/gitlab/gitlab.rb`) auto-prunes old local archives, so no manual
cleanup is needed. Set a smaller value if disk space is tight.

---

## 8. User-scope backup for an unprivileged user

```yaml
restic_profile_repositories:
  r1:
    repository: "rest:https://backup.example.com:8000/alice/laptop"
    password: "{{ vault_alice_restic_password }}"
    rest_username: "alice"
    rest_password: "{{ vault_rest_server_alice_password }}"

restic_profile_profiles:
  alice-home:
    repository_ref: r1
    systemd_scope: user
    systemd_user: alice
    on_calendar: "daily"
    randomized_delay_sec: "30min"
    backup:
      sources:
        - /home/alice
        - /home/alice/Documents
      exclude_patterns:
        - "*.tmp"
        - ".cache/"
    retention:
      keep_daily: 14
```

User-scope profiles require `systemd_scope: user` and an explicit
`systemd_user`.  The role deploys config under
`~/.config/restic-profile/`, units under `~/.config/systemd/user/`, and
state under `~/.local/share/restic-profile/`.  Timers start and stop
with the user's session without requiring `root` privileges.

The `restic-profile` CLI automatically resolves config from
`~/.config/restic-profile/restic-profile.toml` when available
(controlled by `$XDG_CONFIG_HOME` and `$RESTIC_PROFILE_CONFIG`).

---

## Global role variables

These affect every profile unless a profile overrides its copy.

| Variable                               | Default   | Meaning                                                      |
| -------------------------------------- | --------- | ------------------------------------------------------------ |
| `restic_profile_state`                 | `present` | Set `absent` to stop timers and remove all managed files     |
| `restic_profile_restic_binary`         | `""`      | Resolves from PATH; set to pin a specific binary             |
| `restic_profile_no_cache`              | `false`   | Add `--no-cache` to every restic invocation                  |
| `restic_profile_retry_lock`            | `""`      | `--retry-lock` duration (incompatible with old restic ≤0.14) |
| `restic_profile_unlock`                | `false`   | Run `restic unlock` before every backup/retention            |
| `restic_profile_systemd_cpu_quota`     | `"100%"`  | CPUQuota= in generated service units                         |
| `restic_profile_pip_install_source`    | `local`   | How to install restic-profile: `local` / `pypi` / `testpypi` |
| `restic_profile_restic_install_source` | `apt`     | How to install restic: `apt` / `go_build` / `existing`       |

See `roles/restic_profile/defaults/main.yaml` for the complete list with comments.

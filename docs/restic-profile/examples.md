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

restic_profile_repositories:
  r1:
    repository: "rest:https://backup.example.com:8000/apps/myapp"
    password: "{{ vault_myapp_restic_password }}"
    rest_username: "myapp"
    rest_password: "{{ vault_rest_server_myapp_password }}"

restic_profile_profiles:
  myapp:
    repository_ref: r1
    on_calendar: "daily"
    randomized_delay_sec: "30min"
    notify_ref: tg
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
    hooks:
      prevalidate:
        - "test -d /srv/myapp || exit 1"
      before:
        - "systemctl stop myapp.service"
      after:
        - "systemctl start myapp.service"
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

## 4. S3-compatible backend

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

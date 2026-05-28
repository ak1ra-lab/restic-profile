# restic-profile examples

This page is the recommended starting point when you deploy `restic_profile`
with Ansible. The code blocks are `host_vars`-style inputs for the role.

Use this page together with:

- [profiles.md](profiles.md) for the field lookup page
- [config.md](config.md) for the TOML rendered from these examples
- [ansible.md](ansible.md) for deployment and validation notes

## Minimal playbook

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

## Scenario 1: REST backend on a backup client

```yaml
# host_vars/backup-client-01/restic-profile.yaml
---
restic_profile_state: present
restic_profile_pip_install_source: local
restic_profile_restic_install_source: go_build
restic_profile_restic_binary: "/usr/local/bin/restic"
# retry_lock is opt-in; keep it empty on older distro packages that do not support it.
restic_profile_retry_lock: "10m"

restic_profile_repositories:
  r1:
    # Repository password should live in Ansible Vault.
    repository: "rest:https://backup.example.com:8000/alice/home-alice"
    password: "{{ vault_restic_home_alice_password }}"

    # REST backend credentials and optional CA pinning.
    rest_username: "alice"
    rest_password: "{{ vault_restic_home_alice_rest_password }}"
    cacert: "/etc/ssl/certs/backup-ca.pem"

restic_profile_profiles:
  home-alice:
    repository_ref: r1

    # The profile name becomes the default tag; set tag explicitly when you want
    # it to stay stable across future renames.
    tag: "home-alice"

    # Role-managed services run as root; restic_binary, no_cache, and retry_lock can override global settings.
    restic_binary: "/usr/local/bin/restic"
    no_cache: true
    retry_lock: "20m"
    # One schedule per profile; if retention is also configured it runs inline
    # after a successful backup.
    on_calendar: "hourly"
    randomized_delay_sec: "15min"

    backup:
      sources:
        - /home/alice
      one_file_system: true

      # Short excludes stay inline.
      exclude_patterns:
        - "*.bak"
        - "*.tmp"

      # Long excludes become /etc/restic-profile/restic-profile-home-alice.exclude.
      # The role also wires that path into the generated TOML as exclude_file.
      exclude_file_content: |
        .cache/
        .local/share/Trash/
        node_modules/
        .venv/
        __pycache__/
        .vscode-server/

    retention:
      keep_hourly: 24
      keep_daily: 14
      keep_weekly: 8
      keep_monthly: 12

    hooks:
      shell: "/bin/bash"
      prevalidate:
        - "mountpoint -q /home/alice"
      before:
        - "systemctl stop myapp.service"
      after:
        - "systemctl start myapp.service"
      failure:
        - "logger -t restic-profile 'home-alice backup failed'"
      success_templates:
        - "{{ playbook_dir }}/templates/restic-profile/hooks.d/home-alice-success-summary.sh.j2"
      success:
        - "logger -t restic-profile 'home-alice backup succeeded'"

    enabled: true
    timer_enabled: true
```

This is the most feature-complete single-host example in the role docs: REST
credentials, an explicit `tag`, inline and file-based excludes, retention,
hooks, timer/runtime overrides, and a go-build-managed `restic` binary.

## Organizing hook files on the control node

Keep hook file paths out of `host_vars` except for the `src` reference itself.
The recommended split is:

- `host_vars/...`: profile data and the `hooks.<phase>_scripts` / `hooks.<phase>_templates` lists
- `playbooks/templates/...`: Jinja-rendered hook scripts such as `.sh.j2`
- `playbooks/files/...`: static hook scripts copied without templating

Example host vars:

```yaml
# host_vars/backup-client-01/restic-profile.yaml
---
restic_profile_repositories:
  r1:
    repository: "rest:https://backup.example.com:8000/alice/home-alice"
    password: "{{ vault_restic_home_alice_password }}"

restic_profile_profiles:
  home-alice:
    repository_ref: r1
    backup:
      sources:
        - /home/alice

    hooks:
      shell: "/usr/bin/bash"
      success_templates:
        - "{{ playbook_dir }}/templates/restic-profile/hooks.d/home-alice-success-summary.sh.j2"
      success_scripts:
        - "{{ playbook_dir }}/files/restic-profile/hooks.d/home-alice-success-audit.sh"
```

Example template file:

```bash
#!/usr/bin/env bash

set -o errexit -o nounset

log_dir=/var/log/restic-profile
mkdir -p "${log_dir}"

profile_name={{ restic_profile_hook_profile_name | tojson }}
phase_name={{ restic_profile_hook_phase | tojson }}

declare -a profile_sources=(
{% for source in restic_profile_hook_profile.backup.sources %}
    {{ source | tojson }}
{% endfor %}
)

{
  printf '[%s] profile=%s phase=%s\n' \
    "$(date --iso-8601=seconds)" \
    "${profile_name}" \
    "${phase_name}"

  for source_dir in "${profile_sources[@]}"; do
    if [[ -e "${source_dir}" ]]; then
      printf '  source: %s\n' "${source_dir}"
    else
      printf '  missing: %s\n' "${source_dir}"
    fi
  done
} >>"${log_dir}/hook-summary.log"
```

`ansible.builtin.template` accepts absolute or relative `src` paths. For role
tasks like this one, relative paths use Ansible task-path search: current role
first, then the task file location, then the current play. That means
`playbooks/templates/...` and `playbooks/files/...` work well, but using
`{{ playbook_dir }}/...` is the least ambiguous option when you want to be sure
which controller-side file will be used.

The generated remote files land under `/etc/restic-profile/hooks.d/` as:

- `/etc/restic-profile/hooks.d/restic-profile-<profile>.<phase>-<seq>.sh`

Those paths are then appended to the matching `hooks.<phase>` array in the
rendered TOML, so the Python runner still just executes hook entries in order.

## Scenario 2: append-only client plus repository-host retention

Backup client:

```yaml
# host_vars/app-node-01/restic-profile.yaml
---
restic_profile_repositories:
  r1:
    repository: "rest:https://backup.example.com:8000/apps/myapp"
    password: "{{ vault_myapp_restic_password }}"
    rest_username: "myapp"
    rest_password: "{{ vault_myapp_rest_password }}"

restic_profile_profiles:
  myapp:
    repository_ref: r1
    tag: "myapp"
    on_calendar: "hourly"
    randomized_delay_sec: "10min"

    backup:
      sources:
        - /srv/myapp
        - /etc/myapp
      # Append-only repository: this profile only creates snapshots.
```

Repository host:

```yaml
# host_vars/backup-repo-01/restic-profile.yaml
---
restic_profile_repositories:
  r1:
    repository: "/srv/restic/apps/myapp"
    password: "{{ vault_myapp_restic_password }}"

restic_profile_profiles:
  myapp_retention:
    repository_ref: r1
    tag: "myapp"
    on_calendar: "daily"
    randomized_delay_sec: "30min"

    retention:
      forget_current_host: false
      prune: true
      keep_hourly: 0
      keep_daily: 14
      keep_weekly: 8
      keep_monthly: 12
```

This split keeps snapshot creation on the application hosts while leaving
retention plus `--prune` to the repository server.

## Scenario 3: S3-compatible backend with a staged rollout

```yaml
# host_vars/db-node-01/restic-profile.yaml
---
restic_profile_repositories:
  s3_db:
    # For S3-compatible backends, put the custom endpoint directly in repository.
    repository: "s3:https://s3.example.com/backups/postgresql"
    password: "{{ vault_postgres_restic_password }}"
    # Keep aws_default_region only when the backend needs an explicit region.
    aws_default_region: "us-east-1"
    aws_access_key_id: "{{ vault_s3_access_key_id }}"
    aws_secret_access_key: "{{ vault_s3_secret_access_key }}"

restic_profile_profiles:
  postgres-basebackup:
    repository_ref: s3_db
    tag: "postgres-basebackup"
    on_calendar: "03:15"
    randomized_delay_sec: "5min"

    backup:
      sources:
        - /var/backups/postgresql
      exclude_patterns:
        - "*.partial"

    retention:
      keep_last: 7
      keep_daily: 7
      keep_weekly: 4

    # Deploy units first, but disable starting the timer
    timer_enabled: false
```

## Scenario 4: GCS with ADC or explicit credentials

```yaml
# host_vars/gce-node-01/restic-profile.yaml
---
restic_profile_repositories:
  gcs_analytics:
    repository: "gs:my-bucket:/analytics"
    password: "{{ vault_analytics_restic_password }}"
    # ADC on GCE/GKE: google_project_id is enough. If you need an explicit key
    # file or an OAuth2 token, set one of the two optional fields below.
    google_project_id: "company-prod"
    # google_application_credentials: "/etc/gcs/analytics-key.json"
    # google_access_token: "{{ vault_analytics_google_access_token }}"

restic_profile_profiles:
  analytics:
    repository_ref: gcs_analytics
    tag: "analytics"
    on_calendar: "daily"

    backup:
      sources:
        - /srv/analytics

    retention:
      keep_daily: 7
      keep_weekly: 4
      keep_monthly: 6
```

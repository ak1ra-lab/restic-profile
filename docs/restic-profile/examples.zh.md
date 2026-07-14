# Ansible host_vars 示例

所有示例都是 `restic_profile` 角色的 `host_vars` 片段。每个字段都有合理的默认值 - 完整参考和内联注释见 `roles/restic_profile/defaults/main.yaml`。

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

## 1. 备份到 REST 服务器的最简配置

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

一个配置文件，一个定时器，无保留策略。`tag` 默认值为配置文件名称 `laptop-home`。

---

## 2. 备份 + 保留策略 + Telegram 通知 + 钩子

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

先执行备份，然后执行内联保留策略（以本机为范围）。成功时 Telegram 会收到快照统计信息和前 N 个最大文件。

在配置文件上设置 `enabled: false` 可在下次运行时停止并移除其单元。设置 `timer_enabled: false` 可部署单元但保持定时器停止状态。

---

## 3. 仓库主机上的纯保留策略

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

无 `backup` 块 - 这是一个纯保留配置文件。`forget_current_host: false` 使其可以管理来自共享同一 tag 的多个备份客户端的快照。

---

## 4. S3 兼容后端与 PostgreSQL

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

S3 端点嵌入在 `repository` URL 中（`s3:https://host/bucket`）。对于 GCS，使用 `gs:bucket-name:/prefix` 并设置 `google_project_id`。

使用 `pg_dumpall` 进行完整集群导出（角色 + 所有数据库），或使用 `pg_dump <dbname>` 导出单个数据库。切勿直接备份 PostgreSQL 数据目录。

---

## 5. MySQL 备份

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

`--single-transaction` 确保 InnoDB 表在不阻塞写入的情况下获得一致性快照。对于 MyISAM，使用 `--lock-tables`。切勿直接备份 `/var/lib/mysql`。

---

## 6. SQLite 备份

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

SQLite 的 `.backup` 命令使用在线备份 API 创建一致性快照。避免在使用中直接复制数据库文件。

---

## 7. GitLab 备份

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

`gitlab:backup:create` 将带时间戳的 tar 包写入 `/var/opt/gitlab/backups`。GitLab 内置的 `gitlab_rails['backup_keep_time']`（默认 `604800` - `/etc/gitlab/gitlab.rb` 中为 7 天）会自动清理旧的本地归档文件，因此无需手动清理。如果磁盘空间紧张，可设置较小的值。

---

## 8. 非特权用户的 user-scope 备份

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

User-scope 配置文件需要 `systemd_scope: user` 和显式的 `systemd_user`。角色将配置部署在 `~/.config/restic-profile/` 下，单元部署在 `~/.config/systemd/user/` 下，状态部署在 `~/.local/share/restic-profile/` 下。定时器随用户会话启动和停止，无需 `root` 权限。

`restic-profile` CLI 在可用时自动从 `~/.config/restic-profile/restic-profile.toml` 解析配置（由 `$XDG_CONFIG_HOME` 和 `$RESTIC_PROFILE_CONFIG` 控制）。

---

## 全局角色变量

以下变量影响所有配置文件，除非配置文件单独覆盖。

| 变量                                   | 默认值    | 含义                                                   |
| -------------------------------------- | --------- | ------------------------------------------------------ |
| `restic_profile_state`                 | `present` | 设置为 `absent` 以停止定时器并移除所有受管理文件       |
| `restic_profile_restic_binary`         | `""`      | 从 PATH 解析；设置为指定特定的二进制文件               |
| `restic_profile_no_cache`              | `false`   | 为每个 restic 调用添加 `--no-cache`                    |
| `restic_profile_retry_lock`            | `""`      | `--retry-lock` 持续时间（与旧版 restic ≤0.14 不兼容）  |
| `restic_profile_unlock`                | `false`   | 在每个备份/保留操作之前运行 `restic unlock`            |
| `restic_profile_systemd_cpu_quota`     | `"100%"`  | 生成的 service 单元中的 CPUQuota=                      |
| `restic_profile_pip_install_source`    | `local`   | 如何安装 restic-profile：`local` / `pypi` / `testpypi` |
| `restic_profile_restic_install_source` | `apt`     | 如何安装 restic：`apt` / `go_build` / `existing`       |

完整列表和注释见 `roles/restic_profile/defaults/main.yaml`。

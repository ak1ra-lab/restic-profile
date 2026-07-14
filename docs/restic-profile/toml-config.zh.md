```toml
# restic-profile.toml - 带详细注释的配置模板
#
# 将此文件复制到 /etc/restic-profile/restic-profile.toml（系统作用域）
# 或 ~/.config/restic-profile/restic-profile.toml（用户作用域），填写你的
# 凭据和路径，然后运行：
#   restic-profile --check           # 验证配置
#   restic-profile --list            # 列出所有配置文件
#   restic-profile <profile>         # 运行配置文件
#   restic-profile <profile> -n      # 空运行（记录命令，不实际执行）
#
# 每个字段均显示其默认值。删除任何你不需要的部分。

# ---- 全局默认值 ----
# 配置文件继承这些值，除非它们设置了单独的覆盖值。
[global]
restic_binary = ""       # 空 = 从 PATH 解析 `restic`
no_cache = false         # 为每次调用添加 --no-cache
retry_lock = ""          # --retry-lock 持续时间，例如 "10m"
                         # 在 restic ≤ 0.14 上留空（不支持）。
unlock = false           # 在每个工作流之前运行 `restic unlock`
template_dir = ""        # 包含自定义 notify_*.md.j2 模板的目录；
                         # 留空使用内置默认模板

# ---- 仓库 ----
# 每个仓库选择一种后端。删除你不需要的示例。

# 本地文件系统
[repositories.local]
repository = "/srv/restic/myhost"
password = "replace-me-with-a-strong-password"

# REST 服务器（支持 append-only，适合多客户端）
[repositories.rest]
repository = "rest:https://backup.example.com:8000/user/hostname"
password = "replace-me"
rest_username = "alice"
rest_password = "replace-me"
cacert = ""              # 可选：自签名 TLS 的 CA 证书路径

# S3 兼容（MinIO、Ceph、AWS S3 等）
# 端点直接写在 repository URL 中：
#   s3:https://s3.example.com/bucket-name
[repositories.s3]
repository = "s3:https://s3.example.com/backups/myhost"
password = "replace-me"
aws_default_region = ""                  # 可选；仅在需要时设置
aws_access_key_id = "AKIAIOSFODNN7EXAMPLE"
aws_secret_access_key = "replace-me"

# Google Cloud Storage
[repositories.gcs]
repository = "gs:my-bucket:/prefix"
password = "replace-me"
google_project_id = "my-gcp-project"
google_application_credentials = ""      # 服务账号 JSON 密钥文件路径
                                         # 在 GCE/GKE 上使用 ADC 时两者都留空
google_access_token = ""                 # 短期 OAuth2 令牌；
                                         # 优先于密钥文件

# 每个仓库的运行环境变量（在子进程级别注入，不会持久化）
# [repositories.rest.env]
# HTTP_PROXY = "http://proxy:8080"
# RESTIC_COMPRESSION = "max"
# RESTIC_PACK_SIZE = "64"

# ---- 通知（可选） ----
# 支持：telegram、dingtalk、wechat。

[notify.telegram]
type = "telegram"
token = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
chat_id = -1001234567890
timeout = 5.0           # 秒；最小 0.1
top_files_limit = 3     # 成功通知中显示的最大文件数；0 = 禁用

[notify.dingtalk]
type = "dingtalk"
access_token = "replace-me"
secret = ""             # 可选：HMAC-SHA256 签名的密钥

[notify.wechat]
type = "wechat"
key = "replace-me"      # 企业微信机器人的 webhook key

# 可选：仅用于通知调用的 HTTP 代理（不影响 restic）
# [notify.telegram.env]
# HTTPS_PROXY = "http://proxy:8080"

# ---- 配置文件 ----
# 每个配置文件在通过 Ansible 部署时对应一个 systemd timer+service 对。
# profile_name 变为：[profiles.profile_name] 和 restic-profile-profile_name.{service,timer}
# 至少需要 [profiles.<name>.backup] 或 [profiles.<name>.retention] 之一。

# --- 示例 A：仅备份 ---
[profiles.home]
repository_ref = "rest"         # 必须匹配 [repositories] 中的键
notify_ref = ""                 # 引用 [notify.*] 渠道，例如 "telegram"
tag = "home"                    # 快照标签；默认值为配置文件名称
on_calendar = "hourly"          # systemd OnCalendar=；留空禁用定时器
randomized_delay_sec = "15min"  # systemd RandomizedDelaySec=

# 按配置文件覆盖（未设置时继承 [global]）：
restic_binary = ""              # 空 = 使用全局值
no_cache = false                # 覆盖全局 --no-cache
retry_lock = ""                 # 覆盖全局 --retry-lock
unlock = false                  # 覆盖全局 unlock

# 可选：配置文件级别的运行时环境变量（在仓库环境变量之后注入；
# 适用于钩子凭据：PGPASSWORD、MYSQL_PWD 等）
# [profiles.home.env]
# PGPASSWORD = "..."
# MYSQL_PWD = "..."

[profiles.home.hooks]
shell = "/bin/sh"               # 每条命令以 shell -c <command> 的方式运行
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
exclude_file = ""               # --exclude-file 的路径（每行一个模式）
one_file_system = false         # 为 restic backup 添加 --one-file-system

# --- 示例 B：备份 + 内联保留策略 ---
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
prune = false               # 为 `restic forget` 添加 --prune
forget_current_host = true  # 内联保留策略强制为 true；
                             # 仅独立的保留策略配置文件使用此选项

# --- 示例 C：独立保留策略（无 backup 块） ---
# 当备份客户端写入共享仓库时，在仓库主机上使用此选项。
[profiles.prune-demo]
repository_ref = "local"
tag = "myapp"                   # 匹配备份客户端使用的 tag
on_calendar = "daily"
randomized_delay_sec = "30min"

[profiles.prune-demo.retention]
keep_last = 0
keep_hourly = 0
keep_daily = 14
keep_weekly = 8
keep_monthly = 12
keep_yearly = 0
prune = true                    # forget 之后执行 restic prune
forget_current_host = false     # 管理来自所有主机的快照
```

# restic-rest-server

用于部署 [rest-server](https://github.com/restic/rest-server) 的 Ansible 角色 —— restic 仓库的 REST 后端。管理二进制安装、systemd 服务和基于 htpasswd 的认证。

参见 `roles/restic_rest_server/defaults/main.yaml` 了解所有变量。

## 最简 playbook

```yaml
---
- name: deploy restic-rest-server
  hosts: backup_servers
  gather_facts: false
  become: true
  tasks:
    - ansible.builtin.import_role:
        name: ak1ra_lab.restic_profile.restic_rest_server
```

## 示例 1：基础 append-only 服务器

```yaml
restic_rest_server_listen: ":8012"
restic_rest_server_backup_dir: /srv/restic
restic_rest_server_append_only: true
restic_rest_server_private_repos: true

restic_rest_server_htpasswd_users:
  - name: alice
    password: "{{ vault_alice_password }}"
  - name: bob
    password: "{{ vault_bob_password }}"
```

备份客户端连接到 `https://backup.example.com:8012/alice/<repo-name>`。

## 示例 2：在 Debian 12 上使用 go_build

```yaml
restic_rest_server_binary_install_source: go_build
restic_rest_server_binary_install_path: /usr/local/bin/restic-rest-server
restic_rest_server_listen: ":8012"
restic_rest_server_backup_dir: /srv/restic
```

当发行版软件包不可用时（如 Debian 12），使用 `go_build`。在 Debian 13 及以上版本中，可通过 `apt` 安装软件包。

## 在仓库主机上执行保留策略

当 `append_only: true` 时，客户端可以创建快照但不能运行 `forget` 或
`prune`。在同一主机上使用 `restic_profile` 角色部署一个纯保留配置文件，指向本地仓库路径：

```yaml
# 在备份服务器上，除 restic_rest_server 之外：
restic_profile_repositories:
  r1:
    repository: "/srv/restic/alice/myapp"
    password: "{{ vault_alice_restic_password }}"

restic_profile_profiles:
  alice-myapp-retention:
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

## 关键变量

| 变量                                   | 默认值                                    | 备注                            |
| ------------------------------------------ | ------------------------------------------ | -------------------------------- |
| `restic_rest_server_listen`                | `":8012"`                                  | 监听地址                   |
| `restic_rest_server_backup_dir`            | `"/srv/restic"`                            | 存储根目录                     |
| `restic_rest_server_append_only`           | `true`                                     | 禁止通过 REST 执行 forget/prune   |
| `restic_rest_server_private_repos`         | `true`                                     | 子目录为私有仓库 |
| `restic_rest_server_htpasswd_file`         | `"/etc/restic-rest-server/users.htpasswd"` |                                  |
| `restic_rest_server_binary_install_source` | `"apt"`                                    | `apt` / `go_build` / `existing`  |
| `restic_rest_server_htpasswd_crypt_scheme` | `"bcrypt"`                                 | 强烈推荐             |

Htpasswd 用户需要目标节点上安装 `python3-passlib` + `python3-bcrypt`（角色会自动安装）。

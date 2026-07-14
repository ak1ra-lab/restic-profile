# restic-profile

基于配置文件的 [restic](https://restic.net/) 自动化工具，通过 Ansible 部署。

本项目是一个 Ansible 集合（`ak1ra_lab.restic_profile`），用于在本地或远程主机上
安装并配置 `restic-profile` CLI：

- **restic-profile** CLI - 读取 TOML 配置文件，运行 `restic backup` / `forget` /
  `prune`，支持钩子与即时通讯通知。
- **restic_profile** 角色 - 部署 CLI、渲染 TOML 配置，并为每个 profile 管理一个
  systemd 定时器（含用户级 `systemd_scope: user`）。
- **restic_rest_server** 角色 - 部署 [rest-server](https://github.com/restic/rest-server)
  实例，提供远程备份存储。

## 使用 Ansible 部署

控制节点需要 Ansible - 参见 [Ansible 工具链](ansible-toolchain.md) 了解基于 uv 的
搭建方式。克隆仓库并把本 collection 及其依赖安装到项目本地目录：

```shell
git clone https://github.com/ak1ra-lab/restic-profile.git
cd restic-profile
ansible-galaxy collection install -r requirements.yaml -p ./.ansible/collections
ansible-galaxy collection install --force --collections-path .ansible/collections .
```

然后从 [restic-profile 示例](restic-profile/examples.md) 中选择一个示例并填写你的
host_vars。若从源码构建 restic（`restic_profile_restic_install_source: go_build`），
控制节点还需要 `go` 工具链。

## 独立 CLI（无需 Ansible）

该 CLI 也发布到 PyPI，可用于手动或 cron 驱动的场景 - 无需 Ansible、root 或 systemd：

```shell
uv tool install restic-profile-cli
restic-profile -c /path/to/my.toml --check
restic-profile -c /path/to/my.toml myprofile
```

可以从 [TOML 配置模板](restic-profile/toml-config.md) 开始。

## 页面

| 你想...                             | 从这里开始                                     |
| ----------------------------------- | ---------------------------------------------- |
| 使用 Ansible 部署备份配置文件       | [Ansible 示例](restic-profile/examples.md)     |
| 搭建 Ansible 工具链                 | [Ansible 工具链](ansible-toolchain.md)         |
| 编写用于非 Ansible 场景的 TOML 配置 | [TOML 配置模板](restic-profile/toml-config.md) |
| 了解 CLI 参数                       | [CLI 参考](restic-profile/cli.md)              |
| 部署备份服务器 (rest-server)        | [restic-rest-server](restic-rest-server.md)    |

参见 `roles/restic_profile/defaults/main.yaml` 了解所有角色变量及其默认值。

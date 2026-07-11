# restic-profile

基于配置文件的 [restic](https://restic.net/) 自动化工具 —— Python CLI + Ansible 角色。

- **restic-profile** CLI：读取 TOML 配置文件，运行 `restic backup` / `forget` / `prune`，支持钩子和即时通讯通知。
- **restic_profile** Ansible 角色：部署 CLI，渲染 TOML 配置，为每个备份配置文件管理一个 systemd 定时器。支持 `systemd_scope: user` 的用户级部署。
- **restic_rest_server** Ansible 角色：部署 [rest-server](https://github.com/restic/rest-server) 实例，提供远程备份存储。

## 安装

### 独立 CLI（无需 Ansible、root 或 systemd）

```shell
uv tool install restic-profile-cli
```

然后编写配置文件 —— 可以从 [TOML 配置模板](restic-profile/toml-config.md) 开始 ——
然后交互式运行：

```shell
restic-profile -c /path/to/my.toml --check
restic-profile -c /path/to/my.toml myprofile
restic-profile -c /path/to/my.toml myprofile -n
```

不涉及 systemd 定时器；你可以手动调用 CLI 或将其包装在 cron 中。

### Ansible 部署

本仓库是一个 Ansible 集合。将其克隆到标准命名空间布局下：

```shell
mkdir -p collections/ansible_collections/ak1ra_lab
cd collections/ansible_collections/ak1ra_lab
git clone https://github.com/ak1ra-lab/restic-profile.git restic_profile
```

该角色依赖 **ak1ra_lab.general.pyproject_install** 角色。将其一并安装：

```shell
cd collections/ansible_collections/ak1ra_lab
git clone https://github.com/ak1ra-lab/ansible-collection-general.git general
```

或通过 `ansible-galaxy` 安装依赖：

```shell
ansible-galaxy collection install -r requirements.yml
```

附带的 `ansible.cfg` 要求仓库恰好位于 4 层目录深度
（`collections/ansible_collections/ak1ra_lab/restic_profile/ansible.cfg`）。如果你的检出路径不同，请调整 `ansible.cfg` 中的 `collections_path`。

现在从 [restic-profile 示例](restic-profile/examples.md) 中选择一个示例并填写你的 host_vars。

## 页面

| 你想...                              | 从这里开始                                            |
| ------------------------------------------- | ----------------------------------------------------- |
| 使用 Ansible 部署备份配置文件         | [Ansible 示例](restic-profile/examples.md)        |
| 编写用于非 Ansible 场景的 TOML 配置 | [TOML 配置模板](restic-profile/toml-config.md) |
| 了解 CLI 参数                        | [CLI 参考](restic-profile/cli.md)                |
| 部署备份服务器 (rest-server)        | [restic-rest-server](restic-rest-server.md)     |

参见 `roles/restic_profile/defaults/main.yaml` 了解所有角色变量及其默认值。

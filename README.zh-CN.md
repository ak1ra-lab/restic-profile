# restic-profile

[English](https://github.com/ak1ra-lab/restic-profile/blob/master/README.md) | **简体中文**

[![GitHub Actions Workflow Status](https://img.shields.io/github/actions/workflow/status/ak1ra-lab/restic-profile/.github%2Fworkflows%2Fpublish-to-pypi.yaml)](https://github.com/ak1ra-lab/restic-profile/actions/workflows/publish-to-pypi.yaml)
[![PyPI - Version](https://img.shields.io/pypi/v/restic-profile-cli)](https://pypi.org/project/restic-profile-cli/)
[![Docs](https://img.shields.io/badge/docs-online-0a7ea4)](https://ak1ra-lab.github.io/restic-profile/)

基于配置文件的 [restic](https://restic.net/) 自动化工具，通过 Ansible 部署。

本仓库是一个 Ansible 集合（`ak1ra_lab.restic_profile`），以及它安装的
`restic-profile` CLI：

- **restic-profile** - 读取 TOML 配置，运行 `restic backup` / `forget` /
  `prune`，支持钩子与即时通讯通知。
- **restic_profile** 角色 - 部署 CLI、渲染 TOML 配置，并为每个 profile 管理一个
  systemd 定时器（含用户级 `systemd_scope: user`）。
- **restic_rest_server** 角色 - 部署 [rest-server](https://github.com/restic/rest-server)
  实例，提供远程备份存储。

## 安装 CLI

CLI 可独立使用，不需要 Ansible、root 或 systemd；但需要安装 `restic` 并确保它在
`PATH` 中：

```shell
uv tool install restic-profile-cli
restic-profile --help
```

从 [TOML 配置模板][toml] 开始。

## 使用 Ansible 部署

```shell
git clone https://github.com/ak1ra-lab/restic-profile.git
cd restic-profile
ansible-galaxy collection install -r requirements.yaml -p ./.ansible/collections
ansible-galaxy collection install --force --collections-path .ansible/collections .
```

从 [Ansible 示例][examples] 中选择一个示例，填写 `host_vars` 后运行 playbook。
控制节点搭建参见 [Ansible 工具链][toolchain]；若从源码构建 restic
（`restic_profile_restic_install_source: go_build`），还需要 `go` 工具链。

## 文档

完整文档：<https://ak1ra-lab.github.io/restic-profile/zh/>

- [Ansible 示例][examples]
- [TOML 配置模板][toml]
- [CLI 参考][cli]
- [restic-rest-server][server]
- [Ansible 工具链][toolchain]

## 开发

```shell
uv sync --group dev
just lint
just typecheck
just test
```

Ansible、Molecule 与文档工作流见
[AGENTS.md](https://github.com/ak1ra-lab/restic-profile/blob/master/AGENTS.md)。

[examples]: https://ak1ra-lab.github.io/restic-profile/zh/restic-profile/examples/
[toml]: https://ak1ra-lab.github.io/restic-profile/zh/restic-profile/toml-config/
[cli]: https://ak1ra-lab.github.io/restic-profile/zh/restic-profile/cli/
[server]: https://ak1ra-lab.github.io/restic-profile/zh/restic-rest-server/
[toolchain]: https://ak1ra-lab.github.io/restic-profile/zh/ansible-toolchain/

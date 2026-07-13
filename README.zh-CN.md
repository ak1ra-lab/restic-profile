# restic-profile

[English](README.md) | **简体中文**

[![GitHub Actions Workflow Status](https://img.shields.io/github/actions/workflow/status/ak1ra-lab/restic-profile/.github%2Fworkflows%2Fpublish-to-pypi.yaml)](https://github.com/ak1ra-lab/restic-profile/actions/workflows/publish-to-pypi.yaml)
[![PyPI - Version](https://img.shields.io/pypi/v/restic-profile-cli)](https://pypi.org/project/restic-profile-cli/)
[![PyPI - Version](https://img.shields.io/pypi/v/restic-profile-cli?label=test-pypi&pypiBaseUrl=https%3A%2F%2Ftest.pypi.org)](https://test.pypi.org/project/restic-profile-cli/)
[![Docs](https://img.shields.io/badge/docs-online-0a7ea4)](https://ak1ra-lab.github.io/restic-profile/)

基于配置文件的 restic 自动化工具，通过 Ansible 部署。

本仓库是一个 Ansible 集合（`ak1ra_lab.restic_profile`），用于在本地或远程主机上
安装并配置 `restic-profile` CLI：

- **restic-profile** CLI —— 读取 TOML 配置文件，运行 `restic backup` / `forget` /
  `prune`，支持钩子与即时通讯通知。
- **restic_profile** 角色 —— 部署 CLI、渲染 TOML 配置，并为每个 profile 管理一个
  systemd 定时器（含用户级 `systemd_scope: user`）。
- **restic_rest_server** 角色 —— 部署 [rest-server][rs] 实例，提供远程备份存储。

## 使用 Ansible 部署

控制节点需要 Ansible —— 参见 [Ansible 工具链](docs/ansible-toolchain.zh.md) 了解基于
uv 的搭建方式。克隆仓库并把本 collection 及其依赖安装到项目本地目录：

```shell
git clone https://github.com/ak1ra-lab/restic-profile.git
cd restic-profile
ansible-galaxy collection install -r requirements.yaml -p ./.ansible/collections
ansible-galaxy collection install --force --collections-path .ansible/collections .
```

然后从 [Ansible 示例](docs/restic-profile/examples.zh.md) 中选择一个示例，填写你的
host_vars，再运行 playbook。若从源码构建 restic
（`restic_profile_restic_install_source: go_build`），控制节点还需要 `go` 工具链。

## 开发

仅在需要修改 `src/restic_profile` 或角色、插件时才需要：

```shell
uv sync --group dev
just lint
just typecheck
just test
ansible-lint
```

如需与本仓库一起开发 `ak1ra_lab.general`，把 [ansible-collection-general][acg]
克隆到本仓库同级目录，再运行 `just ansible-collection-install` —— 它会安装本
collection 以及你本地的 `../ansible-collection-general`（`ansible.posix`、
`community.general` 则来自用户级别的 Ansible）。

## 文档

<https://ak1ra-lab.github.io/restic-profile/> —— 文档配置存储在 `mkdocs.yml` 中。

[rs]: https://github.com/restic/rest-server
[acg]: https://github.com/ak1ra-lab/ansible-collection-general

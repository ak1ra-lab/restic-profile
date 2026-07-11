# restic-profile

[English](README.md) | **简体中文**

[![GitHub Actions Workflow Status](https://img.shields.io/github/actions/workflow/status/ak1ra-lab/restic-profile/.github%2Fworkflows%2Fpublish-to-pypi.yaml)](https://github.com/ak1ra-lab/restic-profile/actions/workflows/publish-to-pypi.yaml)
[![PyPI - Version](https://img.shields.io/pypi/v/restic-profile-cli)](https://pypi.org/project/restic-profile-cli/)
[![PyPI - Version](https://img.shields.io/pypi/v/restic-profile-cli?label=test-pypi&pypiBaseUrl=https%3A%2F%2Ftest.pypi.org)](https://test.pypi.org/project/restic-profile-cli/)
[![Docs](https://img.shields.io/badge/docs-online-0a7ea4)](https://ak1ra-lab.github.io/restic-profile/)

# restic-profile

基于配置文件的 restic 自动化工具，支持 Ansible 部署。

包含 `restic-profile` Python CLI 以及用于 `restic-profile` 和 `restic-rest-server` 部署的 Ansible 角色。

## 安装

```shell
uv sync --group dev
```

## 可选的 Ansible 工具链

如需使用 Ansible 角色，可在用户级别安装工具链一次：

```shell
uv tool install ansible-dev-tools --with ansible \
	--with-executables-from ansible-builder,ansible-core,ansible-creator,ansible-dev-environment,ansible-lint,ansible-navigator,ansible-sign,molecule
```

日常 Ansible 验证目前使用 `ansible-lint`。Molecule 场景保留在仓库中作为闲置资产，不属于支持的验证流程。

如果你使用 `roles/go_build` 或 `playbooks/go_build/` 下的 playbook，控制节点还需要在 `PATH` 中有可用的 `go` 工具链。

## 仓库开发流程

将 collections 克隆到 `ansible_collections/ak1ra_lab/` 命名空间布局：

```shell
mkdir -p ~/code/github.com/ansible/collections/ansible_collections/ak1ra_lab
git clone https://github.com/ak1ra-lab/ansible-collection-general.git \
	~/code/github.com/ansible/collections/ansible_collections/ak1ra_lab/general
git clone https://github.com/ak1ra-lab/restic-profile.git \
	~/code/github.com/ansible/collections/ansible_collections/ak1ra_lab/restic_profile
```

## 用法

```shell
uv run restic-profile --help
```

对于 Ansible 管理的备份服务器，请参见 `restic_rest_server` 角色和 `docs/restic-rest-server/` 下的文档。

## 开发

```shell
just lint
just typecheck
just test
just docs-build
ansible-lint
```

## 文档

已发布的文档站点位于 <https://ak1ra-lab.github.io/restic-profile/>，本地文档配置存储在 `mkdocs.yml` 中。

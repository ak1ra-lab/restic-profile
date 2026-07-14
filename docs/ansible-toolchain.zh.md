# Ansible 工具链

与具体项目无关的说明：如何用 `uv` 搭建 Ansible 开发工具链，以及 `ansible-lint`
如何解析 collection 路径。可以把本页直接复制到任何附带 Ansible 集合的仓库中。

## 用 uv 安装工具链

[ansible-dev-tools][adt] 将 `ansible-lint`、`ansible-navigator`、`molecule`、
`ansible-creator` 等工具捆绑在单一的 `adt` 入口点之后。上游文档使用 `pip`/`pipx`
安装；下面的 `uv` 方式与之等价，并把一切放进单一的 uv 管理工具环境中：

```shell
uv tool install ansible-dev-tools \
  --with-executables-from ansible-builder \
  --with-executables-from ansible-core \
  --with-executables-from ansible-creator \
  --with-executables-from ansible-dev-environment \
  --with-executables-from ansible-lint \
  --with-executables-from ansible-navigator \
  --with-executables-from ansible-sign \
  --with-executables-from molecule \
  --with molecule-plugins[podman] \
  --with ansible
```

- `--with-executables-from` 将每个捆绑工具自身的入口点暴露到 `PATH`
  （否则只会链接 `adt`）。
- `--with ansible` 会在 `ansible-core` 之外额外安装完整的 `ansible` PyPI 包
  （batteries-included 的 collection 集合），因此 `ansible.posix`、
  `community.general` 等常见 Galaxy collection 可在用户级别解析，无需每个项目各存一份。
- 按需追加更多运行时依赖，例如
  `--with boto3 --with google-auth --with proxmoxer`。

用 `adt --version` 查看版本。

!!! note
上面的 `uv tool install` 命令**并未**记录在上游文档中 - 这是社区总结的用法。
受支持的安装方式请参见[官方安装文档][adt]。

## 自包含的 collection 路径

要让仓库的 Ansible 配置保持隔离 - 绝不触及用户级别或上级目录 - 在项目本地的
`ansible.cfg` 中固定这些路径：

```ini
[defaults]
roles_path=./roles
collections_path=./.ansible/collections
```

把 collection 的依赖安装到该目录树。如果 playbook 通过 FQCN
（`namespace.collection.*`）引用 collection 自身的角色，也把该 collection 本身
安装进去：

```shell
ansible-galaxy collection install -r requirements.yaml -p ./.ansible/collections
ansible-galaxy collection install --force --collections-path .ansible/collections .
```

## ansible-lint 把 collection 安装到哪里

在自动安装 `requirements.yml` / `requirements.yaml` 时，`ansible-lint`
**不会**遵循 `ansible.cfg` 中的 `collections_path`。它内部使用 `ansible-compat`，
后者根据**项目目录**推导出一个缓存目录：

- 从项目根目录运行（非 `offline` 模式）时，它会安装到 `./.ansible/collections`
  - 无论 `collections_path` 设为什么。
- ansible-lint 配置中的 `offline: true` 会完全禁用该自动安装。
- 如果项目根目录不可写，则回退到临时目录。

因此把 `collections_path` 固定为 `./.ansible/collections` 恰好与 `ansible-lint`
自身的行为一致：lint 与 playbook 运行共享同一份 collection 目录树，且不会泄漏到
用户级别的 `~/.ansible`。

[adt]: https://ansible.readthedocs.io/projects/dev-tools/

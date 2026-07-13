# CLI 参考

```text
restic-profile [--config PATH] [--dry-run [{all,notify}]] PROFILE
restic-profile --check [--config PATH]
restic-profile --list [--config PATH]
restic-profile --unlock [--config PATH] [--dry-run] PROFILE
```

| 参数                       | 别名        | 说明                                                                                             |
| -------------------------- | ------------ | --------------------------------------------------------------------------------------------------- |
| `--config PATH`            | `-c`         | 配置文件路径。省略时依次搜索 ``$RESTIC_PROFILE_CONFIG``、``$XDG_CONFIG_HOME/restic-profile/restic-profile.toml``、``/etc/restic-profile/restic-profile.toml`` |
| `--check`                  | `-C`         | 解析并验证配置文件，然后退出                                                            |
| `--list`                   | `-l`         | 打印配置文件列表（名称、类型、计划、仓库）                                              |
| `--unlock PROFILE`         | `-U`         | 为配置文件的仓库解除过期 restic 锁                                              |
| `--dry-run [{all,notify}]` | `-n`         | `all`（默认）：仅记录日志不执行。`notify`：空运行子进程但发送真实通知 |
| `PROFILE`                  | (位置参数) | 要执行的配置文件名                                                               |

`--check`、`--list` 和 `--unlock` 互斥。不能同时使用配置文件名称与其中任何一个。

```shell
# 运行配置文件
restic-profile myapp
restic-profile myapp --dry-run                 # 空运行所有
restic-profile myapp --dry-run notify          # 空运行 + 真实通知
restic-profile myapp --config /path/to/custom.toml

# 验证配置
restic-profile --check
restic-profile --check --config /path/to/custom.toml

# 列出配置文件
restic-profile --list

# 解除过期锁
restic-profile --unlock myapp
restic-profile --unlock myapp --dry-run
```

## Shell 补全

```bash
# bash — 添加到 ~/.bashrc
if command -v register-python-argcomplete >/dev/null 2>&1; then
    eval "$(register-python-argcomplete restic-profile)"
fi

# zsh — 添加到 ~/.zshrc (需要 bashcompinit)
autoload -U +X bashcompinit && bashcompinit
if command -v register-python-argcomplete >/dev/null 2>&1; then
    eval "$(register-python-argcomplete restic-profile)"
fi
```

或使用 `activate-global-python-argcomplete` 进行系统级补全：

```bash
# 按用户安装
activate-global-python-argcomplete --user

# 系统级安装
sudo activate-global-python-argcomplete
```

这会将补全脚本写入全局位置，因此不需要 `.bashrc`/`.zshrc` 片段。

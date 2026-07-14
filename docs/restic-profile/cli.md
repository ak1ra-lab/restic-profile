# CLI reference

```text
restic-profile [--config PATH] [--dry-run [{all,notify}]] PROFILE
restic-profile --check [--config PATH]
restic-profile --list [--config PATH]
restic-profile --unlock [--config PATH] [--dry-run] PROFILE
```

| Flag                       | Alias        | Purpose                                                                                                                                                                  |
| -------------------------- | ------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `--config PATH`            | `-c`         | Config file. When omitted, searches `$RESTIC_PROFILE_CONFIG`, then `$XDG_CONFIG_HOME/restic-profile/restic-profile.toml`, then `/etc/restic-profile/restic-profile.toml` |
| `--check`                  | `-C`         | Parse and validate the config, then exit                                                                                                                                 |
| `--list`                   | `-l`         | Print profile table (name, type, schedule, repository)                                                                                                                   |
| `--unlock PROFILE`         | `-U`         | Remove stale restic locks for the profile's repository                                                                                                                   |
| `--dry-run [{all,notify}]` | `-n`         | `all` (default): log without executing. `notify`: dry-run subprocesses but send a real notification                                                                      |
| `PROFILE`                  | (positional) | Profile name in the config to execute                                                                                                                                    |

`--check`, `--list`, and `--unlock` are mutually exclusive. Combining a profile
name with any of them is rejected.

```shell
# Run a profile
restic-profile myapp
restic-profile myapp --dry-run                 # dry-run all
restic-profile myapp --dry-run notify          # dry-run + real notification
restic-profile myapp --config /path/to/custom.toml

# Validate config
restic-profile --check
restic-profile --check --config /path/to/custom.toml

# List profiles
restic-profile --list

# Remove stale locks
restic-profile --unlock myapp
restic-profile --unlock myapp --dry-run
```

## Shell completion

```bash
# bash - add to ~/.bashrc
if command -v register-python-argcomplete >/dev/null 2>&1; then
    eval "$(register-python-argcomplete restic-profile)"
fi

# zsh - add to ~/.zshrc (bashcompinit required)
autoload -U +X bashcompinit && bashcompinit
if command -v register-python-argcomplete >/dev/null 2>&1; then
    eval "$(register-python-argcomplete restic-profile)"
fi
```

Or use `activate-global-python-argcomplete` for system-wide completion:

```bash
# per-user install
activate-global-python-argcomplete --user

# system-wide install
sudo activate-global-python-argcomplete
```

This writes a completion script into a global location so no `.bashrc`/`.zshrc`
snippet is needed.

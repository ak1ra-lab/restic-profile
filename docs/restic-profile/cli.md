# CLI reference

```text
restic-profile [-c PATH] [-n [{all,notify}]] PROFILE
restic-profile -C [-c PATH]          # --check
restic-profile -l [-c PATH]          # --list
restic-profile -U [-c PATH] [-n] PROFILE  # --unlock
```

| Flag                       | Alias        | Purpose                                                                                             |
| -------------------------- | ------------ | --------------------------------------------------------------------------------------------------- |
| `--config PATH`            | `-c`         | Config file.  When omitted, searches ``$RESTIC_PROFILE_CONFIG``, then ``$XDG_CONFIG_HOME/restic-profile/restic-profile.toml``, then ``/etc/restic-profile/restic-profile.toml`` |
| `--check`                  | `-C`         | Parse and validate the config, then exit                                                            |
| `--list`                   | `-l`         | Print profile table (name, type, schedule, repository)                                              |
| `--unlock PROFILE`         | `-U`         | Remove stale restic locks for the profile's repository                                              |
| `--dry-run [{all,notify}]` | `-n`         | `all` (default): log without executing. `notify`: dry-run subprocesses but send a real notification |
| `PROFILE`                  | (positional) | Profile name in the config to execute                                                               |

`--check`, `--list`, and `--unlock` are mutually exclusive. Combining a profile
name with any of them is rejected.

```shell
# Run a profile
restic-profile myapp
restic-profile myapp -n                    # dry-run all
restic-profile myapp -n notify             # dry-run + real notification
restic-profile myapp -c /path/to/custom.toml

# Validate config
restic-profile -C
restic-profile -C -c /path/to/custom.toml

# List profiles
restic-profile -l

# Remove stale locks
restic-profile -U myapp
restic-profile -U myapp -n
```

## Shell completion

```bash
# bash — add to ~/.bashrc
if command -v register-python-argcomplete >/dev/null 2>&1; then
    eval "$(register-python-argcomplete restic-profile)"
fi

# zsh — add to ~/.zshrc (bashcompinit required)
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

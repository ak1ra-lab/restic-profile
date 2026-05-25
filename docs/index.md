# restic-profile

`restic-profile` is a profile-based `restic` wrapper for Linux backup automation.

This repository also carries the `restic_rest_server` Ansible role so client
profiles and server-side storage automation live together.

The recommended deployment path is the Ansible role `roles/restic_profile`, which
installs the CLI, renders TOML config, and manages systemd units end-to-end.

## Configuration flow

```text
host_vars / group_vars
  -> restic_profile_profiles
  -> roles/restic_profile
      |- /etc/restic-profile/restic-profile.toml
      |- /etc/restic-profile/restic-profile-<name>.env
      |- /etc/restic-profile/restic-profile-<name>.exclude
      |- restic-profile-{backup|forget}-<name>.service
      `- restic-profile-{backup|forget}-<name>.timer
  -> restic-profile CLI
  -> restic
```

The key split in the documentation is:

- `examples.md` shows the Ansible input you write in `host_vars`.
- `config.md` shows the TOML output that the CLI actually reads.
- `profiles.md` is the lookup page for a specific `restic_profile_profiles` field.

The CLI itself is stateless and delegates to `restic`:

- `restic-profile backup PROFILE`
- `restic-profile forget PROFILE`
- `restic-profile validate`
- `restic-profile list`

Credentials are passed to `restic` via environment variables only.

## Start here

- First deployment with the role: [restic-profile/examples.md](restic-profile/examples.md)
- Looking up `restic_profile_profiles` fields: [restic-profile/profiles.md](restic-profile/profiles.md)
- Inspecting generated TOML: [restic-profile/config.md](restic-profile/config.md)
- Understanding CLI behavior: [restic-profile/cli.md](restic-profile/cli.md)
- Role behavior, validation, and security notes: [restic-profile/ansible.md](restic-profile/ansible.md)
- Backup server deployment: [restic-rest-server/index.md](restic-rest-server/index.md)
- Backup server examples: [restic-rest-server/examples.md](restic-rest-server/examples.md)

## Quick install

`restic-profile` is published as its own package:

```shell
uv tool install restic-profile
# or in this repository
just sync
```

The role installs into `/var/lib/restic-profile/venv` and installs
`restic` from APT. It also exposes `/usr/local/bin/restic-profile` as a stable
CLI entry point on the managed host and renders one
`/etc/restic-profile/restic-profile-<name>.env` file per profile for direct
shell sourcing before raw `restic` commands. The role does not modify user
shell startup files; see `docs/restic-profile/ansible.md` for the recommended
workflow.

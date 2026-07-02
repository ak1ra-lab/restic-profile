# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-07-02

### Added

- **`restic-profile` CLI**: a TOML-configurable Python wrapper around `restic`
  that runs backup and retention actions per profile with hook-driven lifecycle
  management.
- **`restic_profile` Ansible role**: deploys the `restic` binary, the
  `restic-profile` Python package, the TOML config, per-repository credential
  env files, per-profile exclude files, hook scripts, and a systemd
  service+timer pair per enabled profile.
- **`restic_rest_server` Ansible role**: deploys a `rest-server` instance for
  hosting restic repositories.
- **Configuration model**: repositories define credentials and URLs; profiles
  reference a repository and carry nested `backup`, `retention`, and `hooks`
  sections.
- **Systemd resource controls**: per-profile `CPUQuota=`, `Nice=`,
  `IOSchedulingClass=`, and `IOSchedulingPriority=` overrides inherited from
  global defaults.
- **`restic-profile-scope` helper**: runs `restic-profile` in a transient
  `systemd-run --scope` with the same resource controls as managed timer
  services for interactive use.
- **Hook system**: supports inline `hooks.<phase>` commands together with
  file-backed `hooks.<phase>_scripts` and `hooks.<phase>_templates` rendered
  to `/etc/restic-profile/hooks.d/`.
- **Storage backend support**: local paths, REST server, S3-compatible, and
  Google Cloud Storage.
- **Multiple install sources**:
  - `restic` binary: `apt`, `go_build` (control-node build), or `existing`.
  - `restic-profile` Python package: `local` (control-node wheel build),
    `pypi`, or `testpypi`.
- **Preflight validation**: catch missing repository credentials, malformed
  profiles, empty backup sources, and idle retention blocks before writing
  any files.
- **State management**: `restic_profile_state: absent` tears down all managed
  systemd units, config files, hook scripts, and the venv.
- **Orphan unit cleanup**: automatically stops, disables, and removes systemd
  units for profiles removed or renamed in `restic_profile_profiles` during a
  normal `state: present` run.
- Full Python test suite with type checking (`ty`) and Ansible lint coverage.

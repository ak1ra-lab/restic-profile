# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.1] - 2026-07-07

### Fixed

- Orphaned `.exclude` and `.env` file cleanup could incorrectly delete all
  managed files due to intermediate `regex_replace` path construction.
  Rewritten to build absolute paths directly in the Jinja2 template.

## [0.2.0] - 2026-07-07

### Added

- Runtime environment variable injection at repository level
  (`[repositories.<name>.env]`) for restic-native settings such as
  `RESTIC_COMPRESSION`, `RESTIC_PACK_SIZE`, and `HTTP_PROXY`
- Runtime environment variable injection at profile level
  (`[profiles.<name>.env]`) for hook credentials such as `PGPASSWORD`,
  `MYSQL_PWD` — applied after repository env so profile env takes precedence
- Runtime environment variable injection at notify channel level
  (`[notify.<name>.env]`) for proxy settings that only affect notification
  HTTP calls
- IM success/failure notifications via Telegram, DingTalk, and WeChat with
  snapshot diff stats, repository stats, and top-N largest files

### Changed

- Replace `Any` with strict `TypedDict`s for Restic JSON data parsing in
  the notify module
- Reorganize `Profile` model field order and docs by semantic groups:
  external refs, scheduling, runtime overrides, env+hooks, tasks

### Fixed

- Preserve progress bar during interactive execution
- Clean up orphaned `.exclude` files alongside `.env` files when profiles
  are disabled or their `exclude_file_content` is cleared
- Improve error handling in hook failure notifications

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
- **Stale lock handling**: `restic-profile --unlock <name>` CLI flag for
  manual stale lock removal, plus per-profile `unlock` config field that
  automatically runs `restic unlock` before backup/retention to prevent
  interrupted processes from blocking future jobs.
- Full Python test suite with type checking (`ty`) and Ansible lint coverage.

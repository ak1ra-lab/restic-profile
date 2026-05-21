from __future__ import annotations

import tomllib
from pathlib import Path

from pydantic import BaseModel, Field, model_validator


class HooksConfig(BaseModel):
    """Per-profile hook commands executed around the backup lifecycle.

    Each hook field is a list of shell command strings (or multi-line scripts).
    Commands are executed via *shell* so pipelines and shell builtins work as
    expected.  If any command in a hook phase exits non-zero, that phase is
    considered failed.

    Lifecycle order::

        prevalidate → (check location) → before → backup → after → success|failure

    If *prevalidate* or *before* fails the backup and *after* hooks are
    skipped; only the *failure* hooks run.
    """

    shell: str = "/bin/sh"
    prevalidate: list[str] = Field(default_factory=list)
    before: list[str] = Field(default_factory=list)
    after: list[str] = Field(default_factory=list)
    failure: list[str] = Field(default_factory=list)
    success: list[str] = Field(default_factory=list)


class RetentionPolicy(BaseModel):
    """Restic snapshot retention policy (keep_* fields)."""

    keep_last: int = 0
    keep_hourly: int = 6
    keep_daily: int = 7
    keep_weekly: int = 4
    keep_monthly: int = 3
    keep_yearly: int = 0


class Profile(BaseModel):
    """A single restic-profile configuration entry."""

    name: str = ""

    # Repository (required)
    repository: str = ""
    password: str = ""

    # REST backend auth (optional)
    rest_username: str = ""
    rest_password: str = ""
    cacert: str = ""

    # S3 credentials (optional)
    aws_default_region: str = ""
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""

    # GCS credentials (optional)
    # google_project_id is required when using a gs: repository.
    # google_application_credentials and google_access_token are both optional:
    # in environments with Application Default Credentials (e.g. GCE instances
    # with the correct OAuth2 scopes) neither needs to be set explicitly.
    # If google_access_token is set it takes precedence and all other GCS auth
    # mechanisms are disabled (note: tokens are short-lived, typically ~1 hour).
    google_project_id: str = ""
    google_application_credentials: str = ""
    google_access_token: str = ""

    # Backup settings
    sources: list[str] = Field(default_factory=list)
    tag: str = ""  # defaults to profile name via model_validator
    exclude_patterns: list[str] = Field(default_factory=list)
    # Path to an exclude file passed via --exclude-file.
    # The Ansible role sets this automatically when exclude_file_content is provided;
    # it can also be set directly in the TOML for manually managed exclude files.
    exclude_file: str = ""
    one_file_system: bool = False
    forget: bool = True
    forget_current_host: bool = False
    prune: bool = False

    # Retention policy
    keep_last: int = 0
    keep_hourly: int = 6
    keep_daily: int = 7
    keep_weekly: int = 4
    keep_monthly: int = 3
    keep_yearly: int = 0

    # Schedule (Ansible / systemd timer)
    on_calendar: str = "hourly"
    randomized_delay_sec: str = "10min"

    # Runtime
    system_user: str = "root"
    restic_binary: str = ""
    no_cache: bool = False
    retry_lock: str = ""

    # Hooks
    hooks: HooksConfig = Field(default_factory=HooksConfig)

    @model_validator(mode="after")
    def _validate_and_set_defaults(self) -> "Profile":
        if not self.tag:
            self.tag = self.name
        if not self.repository:
            raise ValueError(f"Profile {self.name!r}: repository is required")
        if not self.password:
            raise ValueError(f"Profile {self.name!r}: password is required")
        if self.is_retention_only:
            keep_values = [
                self.keep_last,
                self.keep_hourly,
                self.keep_daily,
                self.keep_weekly,
                self.keep_monthly,
                self.keep_yearly,
            ]
            if not any(k > 0 for k in keep_values):
                raise ValueError(
                    f"Profile {self.name!r}: retention-only profile has no retention "
                    "policy (all keep_* values are 0)"
                )
        return self

    @property
    def is_backup(self) -> bool:
        """True when the profile has at least one source path."""
        return len(self.sources) > 0

    @property
    def is_retention_only(self) -> bool:
        """True when the profile has no source paths (retention / forget only)."""
        return len(self.sources) == 0

    @property
    def retention(self) -> RetentionPolicy:
        """Return a RetentionPolicy view of this profile's keep_* fields."""
        return RetentionPolicy(
            keep_last=self.keep_last,
            keep_hourly=self.keep_hourly,
            keep_daily=self.keep_daily,
            keep_weekly=self.keep_weekly,
            keep_monthly=self.keep_monthly,
            keep_yearly=self.keep_yearly,
        )


class ResticProfileConfig(BaseModel):
    """Top-level restic-profile configuration."""

    profiles: dict[str, Profile] = Field(default_factory=dict)


def load_config(path: Path) -> ResticProfileConfig:
    """Load and parse the TOML config at *path*.

    Raises
    ------
    FileNotFoundError
        When *path* does not exist.
    pydantic.ValidationError
        When the TOML content fails schema validation.
    """
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with path.open("rb") as fh:
        data = tomllib.load(fh)

    global_section: dict[str, object] = data.get("global", {})
    global_restic_binary: str = str(global_section.get("restic_binary", ""))
    global_no_cache: bool = bool(global_section.get("no_cache", False))
    global_retry_lock: str = str(global_section.get("retry_lock", ""))

    # Preprocess profiles: inject name from the dict key and propagate
    # global runtime defaults down into each profile because the runners
    # operate on Profile instances directly.
    profiles_data: dict[str, dict] = {}
    for name, pdata in data.get("profiles", {}).items():
        entry = dict(pdata)
        entry.setdefault("name", name)
        if "restic_binary" not in entry:
            entry["restic_binary"] = global_restic_binary
        if "no_cache" not in entry:
            entry["no_cache"] = global_no_cache
        if not entry.get("retry_lock", ""):
            entry["retry_lock"] = global_retry_lock
        # tag defaults to name — handled by model_validator on Profile
        profiles_data[name] = entry

    return ResticProfileConfig.model_validate({"profiles": profiles_data})

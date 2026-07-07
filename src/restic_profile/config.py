from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Annotated, Any, Literal

from chaos_utils.notify.dingtalk import DingTalkBot
from chaos_utils.notify.telegram import TelegramBot
from chaos_utils.notify.wechat import WechatWorkBot
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    TypeAdapter,
    field_validator,
    model_validator,
)


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


class _BaseNotifyConfig(BaseModel):
    """Shared base for per-platform notifier configs."""

    model_config = ConfigDict(extra="forbid")

    env: dict[str, str] = Field(
        default_factory=dict,
        description="Environment variables injected before sending (e.g. HTTP_PROXY).",
    )
    top_files_limit: int = Field(
        default=3,
        ge=0,
        description="Max largest files and diff-changed files in success notification.",
    )


class DingTalkNotifyConfig(_BaseNotifyConfig):
    type: Literal["dingtalk"] = "dingtalk"
    access_token: str = Field(min_length=1)
    secret: str = ""

    def build(self) -> DingTalkBot:
        return DingTalkBot(access_token=self.access_token, secret=self.secret)


class TelegramNotifyConfig(_BaseNotifyConfig):
    type: Literal["telegram"] = "telegram"
    token: str = Field(min_length=1)
    chat_id: int | str
    timeout: float = Field(default=5.0, ge=0.1)
    send_kwargs: dict[str, object] = Field(
        default_factory=dict,
        description="Extra keyword arguments forwarded to send_rich_message / send_message.",
    )

    def build(self) -> TelegramBot:
        return TelegramBot(token=self.token, chat_id=self.chat_id, timeout=self.timeout)


class WechatWorkNotifyConfig(_BaseNotifyConfig):
    type: Literal["wechat"] = "wechat"
    key: str = Field(min_length=1)

    def build(self) -> WechatWorkBot:
        return WechatWorkBot(key=self.key)


NotifierConfig = Annotated[
    DingTalkNotifyConfig | TelegramNotifyConfig | WechatWorkNotifyConfig,
    Field(discriminator="type"),
]


class Repository(BaseModel):
    """A single restic repository definition and credentials."""

    name: str = ""
    repository: str = ""
    password: str = ""

    # REST backend auth
    rest_username: str = ""
    rest_password: str = ""
    cacert: str = ""

    # S3-compatible backend credentials
    aws_default_region: str = ""
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""

    # Google Cloud Storage credentials
    google_project_id: str = ""
    google_application_credentials: str = ""
    google_access_token: str = ""

    env: dict[str, str] = Field(default_factory=dict)

    @field_validator("repository")
    @classmethod
    def validate_repository(cls, v: str) -> str:
        if not v:
            raise ValueError("repository cannot be empty")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if not v:
            raise ValueError("password cannot be empty")
        return v


class BackupConfig(BaseModel):
    """Configurations specific to backing up data sources."""

    sources: list[str] = Field(default_factory=list)
    exclude_patterns: list[str] = Field(default_factory=list)
    exclude_file: str = ""
    one_file_system: bool = False


class RetentionConfig(BaseModel):
    """Configurations specific to snapshot retention (forget & prune)."""

    keep_last: int = 0
    keep_hourly: int = 0
    keep_daily: int = 0
    keep_weekly: int = 0
    keep_monthly: int = 0
    keep_yearly: int = 0
    prune: bool = False
    forget_current_host: bool = True

    @property
    def has_policy(self) -> bool:
        """True when at least one keep_* retention setting is active (nonzero)."""
        return any(
            v > 0
            for v in [
                self.keep_last,
                self.keep_hourly,
                self.keep_daily,
                self.keep_weekly,
                self.keep_monthly,
                self.keep_yearly,
            ]
        )

    @property
    def has_action(self) -> bool:
        """True when the retention block has any actionable setting."""
        return self.has_policy or self.prune


class Profile(BaseModel):
    """A single restic-profile configuration entry."""

    name: str = ""
    repository_ref: str = ""
    tag: str = ""  # snapshot tag; defaults to profile name
    on_calendar: str = ""
    randomized_delay_sec: str = ""

    # Runtime
    restic_binary: str = ""
    no_cache: bool = False
    retry_lock: str = ""
    unlock: bool = False

    # Hooks
    hooks: HooksConfig = Field(default_factory=HooksConfig)

    # Notify
    notify_ref: str = ""

    # Sub-task blocks
    backup: BackupConfig | None = None
    retention: RetentionConfig | None = None

    # Transient runtime resolved state
    resolved_repository: Repository | None = None
    resolved_notifier: NotifierConfig | None = None
    resolved_template_dir: str = ""

    @model_validator(mode="after")
    def _validate_and_set_defaults(self) -> "Profile":
        if not self.tag:
            self.tag = self.name
        if not self.backup and not self.retention:
            raise ValueError(
                f"Profile {self.name!r}: must configure at least one of 'backup' or 'retention'"
            )
        if self.backup and not self.backup.sources:
            raise ValueError(
                f"Profile {self.name!r}: backup section configured but 'sources' list is empty"
            )
        if self.retention and not self.retention.has_action:
            raise ValueError(
                f"Profile {self.name!r}: retention section configured but has no action "
                "(configure keep_* and/or set prune=true)"
            )
        return self

    @property
    def is_backup(self) -> bool:
        """True when the profile has a backup block configured."""
        return self.backup is not None

    @property
    def is_retention_only(self) -> bool:
        """True when the profile only has a retention block configured."""
        return self.backup is None and self.retention is not None

    @property
    def runs_retention(self) -> bool:
        """True when the profile executes a retention step."""
        return self.retention is not None


class ResticProfileConfig(BaseModel):
    """Top-level restic-profile configuration."""

    repositories: dict[str, Repository] = Field(default_factory=dict)
    profiles: dict[str, Profile] = Field(default_factory=dict)
    notify: dict[str, NotifierConfig] = Field(default_factory=dict)
    template_dir: str = ""


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
    global_unlock: bool = bool(global_section.get("unlock", False))
    global_template_dir: str = str(global_section.get("template_dir", ""))

    # Parse repositories
    repositories_data: dict[str, Repository] = {}
    for rname, rdata in data.get("repositories", {}).items():
        entry = dict(rdata)
        entry.setdefault("name", rname)
        repositories_data[rname] = Repository.model_validate(entry)

    # Parse notify channels
    notify_adapter: TypeAdapter[dict[str, NotifierConfig]] = TypeAdapter(
        dict[str, NotifierConfig]
    )
    notify_data: dict[str, NotifierConfig] = {}
    raw_notify: dict[str, Any] = data.get("notify", {})  # type: ignore[assignment]
    if raw_notify:
        notify_data = notify_adapter.validate_python(raw_notify)

    # Parse profiles
    profiles_data: dict[str, Profile] = {}
    for pname, pdata in data.get("profiles", {}).items():
        entry = dict(pdata)
        entry.setdefault("name", pname)
        if "restic_binary" not in entry:
            entry["restic_binary"] = global_restic_binary
        if "no_cache" not in entry:
            entry["no_cache"] = global_no_cache
        if not entry.get("retry_lock", ""):
            entry["retry_lock"] = global_retry_lock
        if "unlock" not in entry:
            entry["unlock"] = global_unlock

        profile = Profile.model_validate(entry)

        # Resolve repository reference
        if not profile.repository_ref:
            raise ValueError(f"Profile {profile.name!r}: repository_ref is required")
        if profile.repository_ref not in repositories_data:
            raise ValueError(
                f"Profile {profile.name!r}: referenced repository {profile.repository_ref!r} not found"
            )

        profile.resolved_repository = repositories_data[profile.repository_ref]

        # Resolve notify reference
        if profile.notify_ref:
            if profile.notify_ref not in notify_data:
                raise ValueError(
                    f"Profile {profile.name!r}: referenced notifier {profile.notify_ref!r} not found"
                )
            profile.resolved_notifier = notify_data[profile.notify_ref]

        profile.resolved_template_dir = global_template_dir

        profiles_data[pname] = profile

    return ResticProfileConfig(
        repositories=repositories_data,
        profiles=profiles_data,
        notify=notify_data,
        template_dir=global_template_dir,
    )

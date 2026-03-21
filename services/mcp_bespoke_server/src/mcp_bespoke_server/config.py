from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    mcp_transport: str = Field(default="stdio", alias="MCP_TRANSPORT")
    mcp_http_host: str = Field(default="127.0.0.1", alias="MCP_HTTP_HOST")
    mcp_http_port: int = Field(default=8000, alias="MCP_HTTP_PORT")
    mcp_allowed_origins: str = Field(default="http://localhost,http://127.0.0.1", alias="MCP_ALLOWED_ORIGINS")
    mcp_auth_token: str | None = Field(default=None, alias="MCP_AUTH_TOKEN")
    allow_admin_tools: bool = Field(default=False, alias="ALLOW_ADMIN_TOOLS")

    bespoke_cmd_host: str = Field(default="127.0.0.1", alias="BESPOKE_CMD_HOST")
    bespoke_cmd_port: int = Field(default=9001, alias="BESPOKE_CMD_PORT")
    reply_listen_host: str = Field(default="127.0.0.1", alias="REPLY_LISTEN_HOST")
    reply_listen_port: int = Field(default=9002, alias="REPLY_LISTEN_PORT")
    telemetry_listen_host: str = Field(default="127.0.0.1", alias="TELEMETRY_LISTEN_HOST")
    telemetry_listen_port: int = Field(default=9010, alias="TELEMETRY_LISTEN_PORT")
    osc_reply_timeout_ms: int = Field(default=1500, alias="OSC_REPLY_TIMEOUT_MS")
    idempotency_ttl_s: int = Field(default=600, alias="IDEMPOTENCY_TTL_S")
    bespoke_known_modules: str = Field(default="", alias="BESPOKE_KNOWN_MODULES")
    bespoke_snapshots_dir: str = Field(default="", alias="BESPOKE_SNAPSHOTS_DIR")

    @property
    def known_modules(self) -> list[str]:
        if not self.bespoke_known_modules.strip():
            return []
        return [item.strip() for item in self.bespoke_known_modules.split(",") if item.strip()]

    @property
    def allowed_origins(self) -> list[str]:
        return [item.strip() for item in self.mcp_allowed_origins.split(",") if item.strip()]


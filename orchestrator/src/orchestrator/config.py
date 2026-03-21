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
    host: str = Field(default="0.0.0.0", alias="ORCHESTRATOR_HOST")
    port: int = Field(default=8088, alias="ORCHESTRATOR_PORT")
    policy_mode: str = Field(default="cloud-ok-no-train", alias="POLICY_MODE")
    consent_required_for_risky: bool = Field(default=True, alias="CONSENT_REQUIRED_FOR_RISKY")
    mcp_client_transport: str = Field(default="http", alias="MCP_CLIENT_TRANSPORT")
    mcp_server_url: str = Field(default="http://127.0.0.1:8000/mcp", alias="MCP_SERVER_URL")
    mcp_server_cmd: str = Field(default="python -m mcp_bespoke_server.server", alias="MCP_SERVER_CMD")
    mcp_client_timeout_s: int = Field(default=10, alias="MCP_CLIENT_TIMEOUT_S")
    default_planner_provider: str = Field(default="mock", alias="DEFAULT_PLANNER_PROVIDER")
    default_summarizer_provider: str = Field(default="mock", alias="DEFAULT_SUMMARIZER_PROVIDER")

    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_base_url: str = Field(default="https://api.openai.com/v1", alias="OPENAI_BASE_URL")
    openai_model: str = Field(default="gpt-5.4-mini", alias="OPENAI_MODEL")

    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    anthropic_base_url: str = Field(default="https://api.anthropic.com/v1", alias="ANTHROPIC_BASE_URL")
    anthropic_model: str = Field(default="claude-sonnet-4-5", alias="ANTHROPIC_MODEL")

    gemini_api_key: str | None = Field(default=None, alias="GEMINI_API_KEY")
    gemini_base_url: str = Field(default="https://generativelanguage.googleapis.com/v1beta", alias="GEMINI_BASE_URL")
    gemini_model: str = Field(default="gemini-2.5-pro", alias="GEMINI_MODEL")

    ollama_base_url: str = Field(default="http://127.0.0.1:11434", alias="OLLAMA_BASE_URL")
    ollama_model: str = Field(default="gemma3", alias="OLLAMA_MODEL")

    llama_cpp_base_url: str = Field(default="http://127.0.0.1:8080/v1", alias="LLAMA_CPP_BASE_URL")
    llama_cpp_model: str = Field(default="local-model", alias="LLAMA_CPP_MODEL")


"""Configuration for the Snowflake + Bedrock GenAI analytics copilot.

Modes:
- DEMO (default when live credentials are absent): SQLite warehouse +
  deterministic local SQL translator. Runs fully offline.
- LIVE: real Snowflake warehouse + real AWS Bedrock LLM. Enabled only when
  ALL required SNOWFLAKE_* and AWS_* variables are present (or APP_MODE=live
  is set explicitly, in which case missing variables raise a clear error).

Credentials come ONLY from environment variables. Nothing is hardcoded and
nothing is read from files.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class SnowflakeConfig:
    account: str = ""
    user: str = ""
    password: str = ""
    role: str = ""
    warehouse: str = ""
    database: str = "GENAI_ANALYTICS"
    schema: str = "PUBLIC"

    @classmethod
    def from_env(cls) -> "SnowflakeConfig":
        return cls(
            account=os.environ.get("SNOWFLAKE_ACCOUNT", ""),
            user=os.environ.get("SNOWFLAKE_USER", ""),
            password=os.environ.get("SNOWFLAKE_PASSWORD", ""),
            role=os.environ.get("SNOWFLAKE_ROLE", ""),
            warehouse=os.environ.get("SNOWFLAKE_WAREHOUSE", ""),
            database=os.environ.get("SNOWFLAKE_DATABASE", "GENAI_ANALYTICS"),
            schema=os.environ.get("SNOWFLAKE_SCHEMA", "PUBLIC"),
        )

    def is_complete(self) -> bool:
        return bool(self.account and self.user and self.password
                    and self.warehouse)


@dataclass
class BedrockConfig:
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_session_token: str = ""
    region: str = "us-east-1"
    model_id: str = "anthropic.claude-3-sonnet-20240229-v1:0"

    @classmethod
    def from_env(cls) -> "BedrockConfig":
        return cls(
            aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID", ""),
            aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY", ""),
            aws_session_token=os.environ.get("AWS_SESSION_TOKEN", ""),
            region=os.environ.get("AWS_REGION", "us-east-1"),
            model_id=os.environ.get(
                "BEDROCK_MODEL_ID",
                "anthropic.claude-3-sonnet-20240229-v1:0",
            ),
        )

    def is_complete(self) -> bool:
        return bool(self.aws_access_key_id and self.aws_secret_access_key)


@dataclass
class AppConfig:
    mode: str = "auto"  # auto | demo | live
    data_path: str = ""
    db_path: str = ""
    project_root: str = ""
    snowflake: SnowflakeConfig = field(default_factory=SnowflakeConfig)
    bedrock: BedrockConfig = field(default_factory=BedrockConfig)

    @classmethod
    def from_env(cls, project_root: str = "") -> "AppConfig":
        root = project_root or os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..")
        return cls(
            mode=os.environ.get("APP_MODE", "auto").lower(),
            data_path=os.environ.get("DATA_PATH", ""),
            db_path=os.environ.get(
                "DB_PATH", os.path.join(root, "data", "warehouse.db")),
            project_root=root,
            snowflake=SnowflakeConfig.from_env(),
            bedrock=BedrockConfig.from_env(),
        )

    def resolve_mode(self) -> str:
        """Return 'live' or 'demo'. Raises in live mode when creds are missing."""
        if self.mode == "live":
            missing = []
            if not self.snowflake.is_complete():
                missing.append(
                    "Snowflake (SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, "
                    "SNOWFLAKE_PASSWORD, SNOWFLAKE_WAREHOUSE)")
            if not self.bedrock.is_complete():
                missing.append(
                    "AWS Bedrock (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)")
            if missing:
                raise ValueError(
                    "APP_MODE=live but credentials are missing: "
                    + "; ".join(missing))
            return "live"
        if self.mode == "demo":
            return "demo"
        # auto: live only when everything is present, else demo.
        if self.snowflake.is_complete() and self.bedrock.is_complete():
            return "live"
        return "demo"

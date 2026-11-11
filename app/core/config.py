import os
from pydantic import SecretStr

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Telecom AIOps AI Service"
    app_version: str = "0.4.0"
    checkpoint_database_url: SecretStr | None = None
    agent_api_key: SecretStr | None = None
    trace_directory: str = "logs/traces"

    spring_boot_base_url: str = "http://127.0.0.1:8080"

    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-flash"

    model_config = SettingsConfigDict(
        env_file=(".env", ".env.agent"),
        env_file_encoding="utf-8",
        case_sensitive=False
    )

    @property
    def deepseek_api_key(self) -> str:
        api_key = os.getenv("DS_API_KEY")

        if not api_key:
            raise RuntimeError(
                "未找到系统环境变量 DS_API_KEY"
            )

        return api_key


settings = Settings()

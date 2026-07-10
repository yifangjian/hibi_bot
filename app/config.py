from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    line_channel_secret: str = ""
    line_channel_access_token: str = ""

    supabase_url: str = ""
    supabase_key: str = ""

    openai_api_key: str = ""
    openai_model: str = "gpt-5.4-mini"

    ai_tutor_daily_turn_limit: int = 10


settings = Settings()

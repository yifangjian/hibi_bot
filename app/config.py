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

    internal_cron_secret: str = ""
    daily_push_enabled: bool = True

    # 開通成功時一起傳給學生的操作說明圖（公開 https 網址，≤1MB 才能兼作預覽圖）；留空就只傳文字
    guide_image_url: str = ""

    gmail_address: str = ""
    gmail_app_password: str = ""
    notify_email: str = ""


settings = Settings()

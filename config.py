from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str
    JWT_SECRET: str
    GOOGLE_CLIENT_ID: str
    FRONTEND_URL: str = "http://localhost:3000"
    ADMIN_EMAIL: str = ""
    OPENAI_API_KEY: str = ""
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    DAILY_API_KEY: str = ""
    COOKIE_SECURE: bool = False
    class Config:
        env_file = ".env"

settings = Settings()

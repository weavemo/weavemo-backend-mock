from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    # Environment
    ENV: str = Field(default="local")

    # Supabase
    SUPABASE_URL: str
    SUPABASE_SERVICE_ROLE_KEY: str

    # JWT (reserved - not used with Supabase Auth)
    SwUPABASE_JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60

    class Config:
        env_file = ".env"
        extra = "forbid"   # 정의 안 된 env 있으면 에러

settings = Settings()

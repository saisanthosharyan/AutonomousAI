from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application configuration loaded from environment variables.
    """

    # --------------------------------------------------
    # Project
    # --------------------------------------------------

    PROJECT_NAME: str = "AutoDev AI"
    PROJECT_VERSION: str = "0.1.0"

    DEBUG: bool = False

    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # --------------------------------------------------
    # LLM Priority
    # --------------------------------------------------

    LLM_PRIORITY: str = "ollama,gemini,openai"

    # --------------------------------------------------
    # Ollama
    # --------------------------------------------------

    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen2.5:3b"

    # --------------------------------------------------
    # OpenAI
    # --------------------------------------------------

    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4.1-mini"

    # --------------------------------------------------
    # Gemini
    # --------------------------------------------------

    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.5-flash"

    # --------------------------------------------------
    # Database
    # --------------------------------------------------

    DATABASE_URL: str = "sqlite:///./autodev.db"

    # --------------------------------------------------
    # Vector Database
    # --------------------------------------------------

    CHROMA_DB_PATH: str = "./chroma_db"

    # --------------------------------------------------
    # Retry Configuration
    # --------------------------------------------------

    MAX_RETRIES: int = 3
    RETRY_DELAY: int = 2

    # --------------------------------------------------
    # Project Generation
    # --------------------------------------------------

    GENERATED_PROJECTS_DIR: str = "../generated_projects"

    # --------------------------------------------------
    # Logging
    # --------------------------------------------------

    LOG_LEVEL: str = "INFO"

    # --------------------------------------------------
    # Environment
    # --------------------------------------------------

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()

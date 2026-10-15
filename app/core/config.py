from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    SUPABASE_URL: str
    SUPABASE_KEY: str
    SUPABASE_SECRET_KEY: str
    SUPABASE_JWKS_URL: str
    OPENAI_API_KEY: str
    LANGSMITH_TRACING: bool = False
    LANGSMITH_API_KEY: str = ""
    LANGSMITH_PROJECT: str = "default"
    LANGSMITH_ENDPOINT: str
    PINECONE_API_KEY: str = ""
    PINECONE_INDEX_NAME: str = ""
    OPENAI_EMBEDDING_MODEL: str = ""
    ADMIN_USER_IDS: str = ""

    class Config:
        env_file = ".env"
        
settings = Settings()
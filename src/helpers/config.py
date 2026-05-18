from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):

    APP_NAME: str 
    APP_VERSION: str

    FILE_ALLOWED_TYPES: list[str]
    FILE_MAX_SIZE: int
    FILE_DEFAULT_CHUNK_SIZE: int

    POSTGRES_HOST: str
    POSTGRES_PORT: int
    POSTGRES_MAIN_DB: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str

    GENERATION_BACKEND: str
    EMBEDDING_BACKEND: str

    OPENAI_API_KEY: str=None
    OPENAI_BASE_URL: str=None

    COHERE_API_KEY: str=None

    GENERATION_MODEL_ID: str=None
    EMBEDDING_MODEL_ID: str=None
    EMBEDDING_MODEL_SIZE: int=None

    DEFAULT_INPUT_MAX_CHARACTERS: int=None
    DEFAULT_OUTPUT_MAX_TOKENS: int=None
    DEFAULT_TEMPERATURE: float=None

    VECTOR_DB_BACKEND_LITERALS: list[str] = None
    VECTOR_DB_BACKEND: str
    VECTOR_DB_PATH: str
    VECTOR_DB_DISTANCE_METHOD: str=None
    VECTOR_DB_PGVEC_INDEX_THRESHOLD: int=100


    PRIMARY_LANGUAGE: str="english"
    DEFAULT_LANGUAGE: str="english"


    class Config:
        env_file = ".env"



def get_settings():
    return Settings()
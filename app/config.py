import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Configuration for OpenRouter service"""

    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
    OPENROUTER_GENERATOR_AGENT: str = os.getenv("OPENROUTER_AGENT", "google/gemini-2.5-flash-preview")
    OPENROUTER_REVIEWER_AGENT: str = os.getenv("OPENROUTER_REVIEWER_AGENT", "google/gemini-2.5-flash-preview")

    # Logging: set LOG_LEVEL=DEBUG or LOG_LEVEL=INFO for verbose output; defaults to WARNING
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "WARNING").upper()

    PORT: int = int(os.getenv("PORT", "8085"))
    CHROMA_PERSIST_DIR: str = os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")
    DOCUMENTS_DIR: str = os.getenv("DOCUMENTS_DIR", "./documents")
    TOP_K_CHUNKS: int = int(os.getenv("TOP_K_CHUNKS", "5"))
    COLLECTION_NAME: str = "vipassana_docs"
    CHUNK_SIZE: int = 600
    CHUNK_OVERLAP: int = 100
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    SOURCES_FILE: str = os.getenv("SOURCES_FILE", "./sources.json")

    @classmethod
    def validate(cls):
        if not cls.OPENROUTER_API_KEY:
            raise ValueError("OPENROUTER_API_KEY environment variable is required")


config = Config()

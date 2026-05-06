from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "MedAssist-CDSS"
    api_key: str = ""
    llm_model: str = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"
    ner_model: str = "d4data/biomedical-ner-all"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    max_followup_iterations: int = 2
    max_followup_questions: int = 3
    confidence_threshold: float = 0.7

    class Config:
        env_file = ".env"


settings = Settings()

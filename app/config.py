from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "MedAssist-CDSS"
    hf_api_token: str = ""
    llm_model: str = "mistralai/Mistral-7B-Instruct-v0.2"
    llm_fallback_model: str = "HuggingFaceH4/zephyr-7b-beta"
    ner_model: str = "d4data/biomedical-ner-all"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    max_followup_iterations: int = 2
    max_followup_questions: int = 3
    confidence_threshold: float = 0.7
    request_timeout: int = 30

    class Config:
        env_file = ".env"


settings = Settings()

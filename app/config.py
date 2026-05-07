import os
import ssl

import urllib3

# Disable SSL verification for corporate proxy environments
os.environ["HF_HUB_DISABLE_SSL_VERIFY"] = "1"
os.environ["CURL_CA_BUNDLE"] = ""
os.environ["REQUESTS_CA_BUNDLE"] = ""
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
ssl._create_default_https_context = ssl._create_unverified_context

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "MedAssist-CDSS"
    api_key: str = ""
    groq_api_key: str = ""
    groq_model: str = "llama-3.1-8b-instant"
    database_url: str = "postgresql+asyncpg://medassist:medassist123@localhost:5437/medassist"
    llm_model: str = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"
    hf_inference_model: str = "Qwen/Qwen2.5-7B-Instruct"
    hf_api_token: str = ""
    ner_model: str = "d4data/biomedical-ner-all"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    max_followup_iterations: int = 2
    max_followup_questions: int = 3
    confidence_threshold: float = 0.7

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()

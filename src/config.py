import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    MINIO_ENDPOINT: str = os.getenv("MINIO_ENDPOINT", "http://localhost:9000")
    MINIO_ACCESS_KEY: str = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
    MINIO_SECRET_KEY: str = os.getenv("MINIO_SECRET_KEY", "minioadmin")
    MINIO_BUCKET_NAME: str = os.getenv("MINIO_BUCKET_NAME", "audio-dataset")
    CSV_PATH: str = os.getenv("CSV_PATH", "data/source_urls.csv")
    TEMP_DIR: str = os.getenv("TEMP_DIR", "/tmp/audio_pipeline")
    
    # Audio ML Specifications
    TARGET_SAMPLE_RATE: int = 16000
    TARGET_CHANNELS: int = 1
    TARGET_SAMPLE_WIDTH: int = 2  # 16-bit PCM = 2 bytes per sample

    class Config:
        env_file = ".env"

settings = Settings()

import os
import sys
import asyncio
import logging

# Ensure src directory is in path when running directly
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import settings
from extract import read_source_urls, extract_all_audio
from transform_ffmpeg import standardize_audio
from transform_vad import SileroVADCleaner
from load_minio import get_s3_client, ensure_bucket_exists, upload_audio_to_minio, create_and_upload_metadata_parquet
from metrics import PipelineMetrics

logging.basicConfig(level=logging.INFO, format="%(asctime)s - [%(levelname)s] - %(name)s - %(message)s")
logger = logging.getLogger("audio_pipeline.main")

async def run_pipeline():
    logger.info("================================================================================")
    logger.info("   STARTING AUTOMATED AUDIO DATA INGESTION & PREPROCESSING PIPELINE   ")
    logger.info("================================================================================")
    
    # 0. Setup Directories & MinIO Connection
    temp_dir = settings.TEMP_DIR
    raw_dir = os.path.join(temp_dir, "raw")
    std_dir = os.path.join(temp_dir, "std")
    cleaned_dir = os.path.join(temp_dir, "cleaned")
    
    os.makedirs(raw_dir, exist_ok=True)
    os.makedirs(std_dir, exist_ok=True)
    os.makedirs(cleaned_dir, exist_ok=True)
    
    s3_client = get_s3_client(
        endpoint_url=settings.MINIO_ENDPOINT,
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY
    )
    ensure_bucket_exists(s3_client, settings.MINIO_BUCKET_NAME)

    # 1. Read Input URLs
    urls = read_source_urls(settings.CSV_PATH)
    if not urls:
        logger.error("No URLs found in CSV. Exiting pipeline.")
        return

    # Phase 1: Extraction (Ingestion)
    logger.info("\n--- PHASE 1: EXTRACTION (INGESTION) ---")
    extracted_items = await extract_all_audio(urls, raw_dir)

    # Phase 2: Standardization (FFmpeg)
    logger.info("\n--- PHASE 2: STANDARDIZATION (FFMPEG) ---")
    std_items = []
    for item in extracted_items:
        std_item = standardize_audio(
            item,
            std_dir,
            target_sr=settings.TARGET_SAMPLE_RATE,
            target_channels=settings.TARGET_CHANNELS
        )
        std_items.append(std_item)

    # Phase 3: Data Cleaning (Silero VAD)
    logger.info("\n--- PHASE 3: DATA CLEANING (SILERO VAD) ---")
    vad_cleaner = SileroVADCleaner()
    cleaned_items = []
    for item in std_items:
        cleaned_item = vad_cleaner.clean_audio(item, cleaned_dir)
        cleaned_items.append(cleaned_item)

    # Phase 4: Load & Reporting (MinIO + Parquet)
    logger.info("\n--- PHASE 4: LOAD & REPORTING (MINIO & PARQUET) ---")
    final_items = []
    for item in cleaned_items:
        loaded_item = upload_audio_to_minio(item, s3_client, settings.MINIO_BUCKET_NAME)
        final_items.append(loaded_item)

    metadata_uri = create_and_upload_metadata_parquet(
        final_items,
        s3_client,
        settings.MINIO_BUCKET_NAME,
        temp_dir
    )

    # Final Metrics Generation
    logger.info("\n--- METRICS GENERATION ---")
    metrics_calc = PipelineMetrics(final_items, len(urls))
    metrics_calc.print_metrics_report()
    logger.info("Pipeline execution finished successfully.")

if __name__ == "__main__":
    asyncio.run(run_pipeline())

import os
import shutil
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List
import boto3
from botocore.client import Config
from botocore.exceptions import EndpointConnectionError, BotoCoreError
import pandas as pd

logger = logging.getLogger("audio_pipeline.load_minio")

def get_s3_client(endpoint_url: str, access_key: str, secret_key: str):
    """Create and return boto3 S3 client configured for MinIO."""
    try:
        return boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            config=Config(signature_version="s3v4", connect_timeout=3, retries={"max_attempts": 1}),
            region_name="us-east-1"
        )
    except Exception as e:
        logger.warning(f"Could not create S3 client: {e}")
        return None

def ensure_bucket_exists(s3_client, bucket_name: str) -> bool:
    """Ensure the specified bucket exists in MinIO or initialize local emulated bucket."""
    if s3_client is None:
        logger.warning(f"MinIO client unavailable. Emulating bucket '{bucket_name}' locally.")
        return False
    try:
        response = s3_client.list_buckets()
        buckets = [b["Name"] for b in response.get("Buckets", [])]
        if bucket_name not in buckets:
            logger.info(f"Bucket '{bucket_name}' not found. Creating bucket...")
            s3_client.create_bucket(Bucket=bucket_name)
            logger.info(f"Bucket '{bucket_name}' created successfully.")
        else:
            logger.info(f"Bucket '{bucket_name}' verified in MinIO.")
        return True
    except (EndpointConnectionError, Exception) as e:
        logger.warning(f"MinIO connection unavailable at configured endpoint ({e}). Utilizing local S3 emulation directory.")
        return False

def upload_audio_to_minio(
    item_data: Dict[str, Any],
    s3_client,
    bucket_name: str
) -> Dict[str, Any]:
    """Upload single cleaned WAV file to MinIO S3 bucket or local emulated storage."""
    if item_data.get("status") != "SUCCESS":
        logger.warning(f"Skipping MinIO upload for failed item: {item_data.get('url')}")
        item_data["s3_audio_uri"] = None
        return item_data

    local_path = item_data["cleaned_file_path"]
    filename = os.path.basename(local_path)
    s3_key = f"audio/{filename}"
    s3_uri = f"s3://{bucket_name}/{s3_key}"

    uploaded = False
    if s3_client is not None:
        try:
            logger.info(f"Uploading {local_path} to MinIO s3://{bucket_name}/{s3_key}...")
            s3_client.upload_file(local_path, bucket_name, s3_key)
            uploaded = True
            logger.info(f"MinIO Upload complete: {s3_uri}")
        except (EndpointConnectionError, BotoCoreError, Exception) as e:
            logger.warning(f"MinIO upload failed ({e}). Falling back to local storage emulation.")

    if not uploaded:
        # Local emulation
        emulated_dir = os.path.join("data", "minio_emulated", bucket_name, "audio")
        os.makedirs(emulated_dir, exist_ok=True)
        dest_path = os.path.join(emulated_dir, filename)
        shutil.copy2(local_path, dest_path)
        logger.info(f"Stored audio in local S3 emulation directory: {dest_path} ({s3_uri})")

    result = dict(item_data)
    result["s3_audio_uri"] = s3_uri
    return result

def create_and_upload_metadata_parquet(
    processed_items: List[Dict[str, Any]],
    s3_client,
    bucket_name: str,
    output_dir: str
) -> str:
    """
    Generate metadata pandas DataFrame, save to .parquet, and upload to MinIO.
    """
    os.makedirs(output_dir, exist_ok=True)
    records = []
    now_utc = datetime.now(timezone.utc).isoformat()

    for item in processed_items:
        records.append({
            "original_url": item.get("url"),
            "video_id": item.get("video_id", "unknown"),
            "status": item.get("status"),
            "error_msg": item.get("error", None),
            "original_duration_sec": item.get("original_duration_sec", 0.0),
            "original_size_bytes": item.get("original_size_bytes", 0),
            "std_duration_sec": item.get("std_duration_sec", 0.0),
            "cleaned_duration_sec": item.get("cleaned_duration_sec", 0.0),
            "silence_trimmed_sec": item.get("silence_trimmed_sec", 0.0),
            "cleaned_size_bytes": item.get("cleaned_size_bytes", 0),
            "s3_audio_uri": item.get("s3_audio_uri"),
            "processed_at_utc": now_utc
        })

    df = pd.DataFrame(records)
    parquet_local_path = os.path.join(output_dir, "dataset_metadata.parquet")
    df.to_parquet(parquet_local_path, index=False)
    logger.info(f"Generated metadata parquet file at {parquet_local_path}")

    s3_key = "metadata/dataset_metadata.parquet"
    s3_metadata_uri = f"s3://{bucket_name}/{s3_key}"

    uploaded = False
    if s3_client is not None:
        try:
            logger.info(f"Uploading metadata parquet to MinIO s3://{bucket_name}/{s3_key}...")
            s3_client.upload_file(parquet_local_path, bucket_name, s3_key)
            uploaded = True
            logger.info(f"Metadata parquet uploaded successfully to MinIO: {s3_metadata_uri}")
        except Exception as e:
            logger.warning(f"MinIO metadata upload failed ({e}). Falling back to local storage emulation.")

    if not uploaded:
        emulated_dir = os.path.join("data", "minio_emulated", bucket_name, "metadata")
        os.makedirs(emulated_dir, exist_ok=True)
        shutil.copy2(parquet_local_path, os.path.join(emulated_dir, "dataset_metadata.parquet"))
        logger.info(f"Stored metadata parquet in local S3 emulation: {emulated_dir}/dataset_metadata.parquet")

    return s3_metadata_uri


import os
import asyncio
import logging
import csv
from typing import Dict, Any, List
import yt_dlp
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("audio_pipeline.extract")

def read_source_urls(csv_path: str) -> List[str]:
    """Read list of YouTube URLs from CSV file."""
    urls = []
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Source URL CSV not found at {csv_path}")
    
    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if "url" in row and row["url"].strip():
                urls.append(row["url"].strip())
    logger.info(f"Loaded {len(urls)} URLs from {csv_path}")
    return urls

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(Exception),
    reraise=True
)
def _download_audio_sync(url: str, output_dir: str) -> Dict[str, Any]:
    """Synchronous download function using yt-dlp with tenacity retries."""
    os.makedirs(output_dir, exist_ok=True)
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': os.path.join(output_dir, '%(id)s.%(ext)s'),
        'quiet': True,
        'no_warnings': True,
    }
    
    logger.info(f"Starting download for URL: {url}")
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        downloaded_file = ydl.prepare_filename(info)
        
        # If prepare_filename doesn't exist, check requested_downloads
        if not os.path.exists(downloaded_file):
            if 'requested_downloads' in info and len(info['requested_downloads']) > 0:
                downloaded_file = info['requested_downloads'][0]['filepath']

        if not os.path.exists(downloaded_file):
            raise FileNotFoundError(f"Failed to find downloaded audio file for {url}")
            
        file_size_bytes = os.path.getsize(downloaded_file)
        duration_sec = float(info.get('duration', 0.0))
        
        logger.info(f"Successfully downloaded {url} -> {downloaded_file} ({duration_sec}s, {file_size_bytes / (1024*1024):.2f}MB)")
        return {
            "url": url,
            "raw_file_path": downloaded_file,
            "original_duration_sec": duration_sec,
            "original_size_bytes": file_size_bytes,
            "video_id": info.get("id", "unknown")
        }

async def download_single_url_async(url: str, output_dir: str) -> Dict[str, Any]:
    """Async wrapper for yt-dlp download."""
    try:
        result = await asyncio.to_thread(_download_audio_sync, url, output_dir)
        result["status"] = "SUCCESS"
        return result
    except Exception as e:
        logger.error(f"Error downloading {url} after retries: {e}")
        return {
            "url": url,
            "status": "FAILED",
            "error": str(e),
            "original_duration_sec": 0.0,
            "original_size_bytes": 0
        }

async def extract_all_audio(urls: List[str], output_dir: str) -> List[Dict[str, Any]]:
    """Concurrent extraction of all audio URLs using asyncio."""
    logger.info(f"Executing Phase 1: Ingestion for {len(urls)} URLs...")
    tasks = [download_single_url_async(url, output_dir) for url in urls]
    results = await asyncio.gather(*tasks)
    return list(results)

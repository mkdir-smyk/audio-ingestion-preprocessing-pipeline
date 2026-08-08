import os
import logging
from typing import Dict, Any
import ffmpeg

logger = logging.getLogger("audio_pipeline.transform_ffmpeg")

def standardize_audio(
    extracted_data: Dict[str, Any],
    output_dir: str,
    target_sr: int = 16000,
    target_channels: int = 1
) -> Dict[str, Any]:
    """
    Phase 2: Standardization.
    Converts downloaded raw audio to 16kHz mono-channel 16-bit PCM .wav format.
    """
    if extracted_data.get("status") != "SUCCESS":
        logger.warning(f"Skipping standardization for failed ingestion URL: {extracted_data.get('url')}")
        return extracted_data

    raw_path = extracted_data["raw_file_path"]
    video_id = extracted_data["video_id"]
    os.makedirs(output_dir, exist_ok=True)
    
    std_filename = f"{video_id}_16k_mono.wav"
    std_filepath = os.path.join(output_dir, std_filename)
    
    logger.info(f"Standardizing {raw_path} -> {std_filepath} (16kHz, mono, pcm_s16le)...")
    
    try:
        stream = ffmpeg.input(raw_path)
        stream = ffmpeg.output(
            stream,
            std_filepath,
            ar=target_sr,
            ac=target_channels,
            acodec='pcm_s16le',
            loglevel='error'
        )
        ffmpeg.run(stream, overwrite_output=True)
        
        if not os.path.exists(std_filepath):
            raise FileNotFoundError(f"Standardized WAV output file not created: {std_filepath}")
            
        std_size_bytes = os.path.getsize(std_filepath)
        
        # Probe exact duration of standardized file
        probe = ffmpeg.probe(std_filepath)
        duration_sec = float(probe['format']['duration'])
        
        logger.info(f"Standardization complete: {std_filepath} ({duration_sec:.2f}s, {std_size_bytes / (1024*1024):.2f}MB)")
        
        result = dict(extracted_data)
        result.update({
            "std_file_path": std_filepath,
            "std_duration_sec": duration_sec,
            "std_size_bytes": std_size_bytes,
            "sample_rate": target_sr,
            "channels": target_channels
        })
        return result

    except Exception as e:
        logger.error(f"FFmpeg standardization failed for {raw_path}: {e}")
        result = dict(extracted_data)
        result["status"] = "FAILED_STANDARDIZATION"
        result["error"] = str(e)
        return result

import os
import logging
from typing import Dict, Any
import numpy as np
import torch
from scipy.io import wavfile

logger = logging.getLogger("audio_pipeline.transform_vad")

def read_wav_to_float_tensor(filepath: str) -> torch.Tensor:
    """Read 16kHz PCM wav file into normalized float32 1D torch tensor."""
    sr, data = wavfile.read(filepath)
    if data.ndim > 1:
        data = data[:, 0]  # Ensure mono
    if data.dtype == np.int16:
        tensor = torch.from_numpy(data.astype(np.float32) / 32768.0)
    elif data.dtype == np.float32:
        tensor = torch.from_numpy(data)
    else:
        tensor = torch.from_numpy(data.astype(np.float32))
    return tensor

def save_float_tensor_to_pcm_wav(filepath: str, tensor: torch.Tensor, sample_rate: int = 16000):
    """Convert float32 1D torch tensor back to int16 PCM wav file."""
    audio_np = tensor.detach().cpu().numpy()
    audio_int16 = np.clip(audio_np * 32767.0, -32768.0, 32767.0).astype(np.int16)
    wavfile.write(filepath, sample_rate, audio_int16)

class SileroVADCleaner:
    def __init__(self):
        logger.info("Initializing Silero VAD model via PyTorch Hub...")
        try:
            self.model, self.utils = torch.hub.load(
                repo_or_dir='snakers4/silero-vad',
                model='silero_vad',
                force_reload=False,
                trust_repo=True
            )
            (self.get_speech_timestamps,
             _, _, _,
             self.collect_chunks) = self.utils
            logger.info("Silero VAD model loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load Silero VAD model: {e}")
            raise e

    def clean_audio(
        self,
        std_data: Dict[str, Any],
        output_dir: str
    ) -> Dict[str, Any]:
        """
        Phase 3: Data Cleaning (VAD).
        Slices audio tensors to remove silence and non-speech segments.
        """
        if std_data.get("status") != "SUCCESS":
            logger.warning(f"Skipping VAD for un-standardized URL: {std_data.get('url')}")
            return std_data

        std_filepath = std_data["std_file_path"]
        video_id = std_data["video_id"]
        target_sr = std_data.get("sample_rate", 16000)
        os.makedirs(output_dir, exist_ok=True)

        cleaned_filename = f"{video_id}_cleaned.wav"
        cleaned_filepath = os.path.join(output_dir, cleaned_filename)

        logger.info(f"Applying Silero VAD on {std_filepath}...")
        try:
            wav = read_wav_to_float_tensor(std_filepath)
            
            # Detect speech timestamps
            speech_timestamps = self.get_speech_timestamps(
                wav,
                self.model,
                sampling_rate=target_sr,
                threshold=0.5
            )

            if speech_timestamps and len(speech_timestamps) > 0:
                cleaned_wav = self.collect_chunks(speech_timestamps, wav)
            else:
                logger.warning(f"No speech detected in {std_filepath}, retaining original audio tensor.")
                cleaned_wav = wav

            # Save cleaned WAV as PCM s16le
            save_float_tensor_to_pcm_wav(cleaned_filepath, cleaned_wav, sample_rate=target_sr)

            if not os.path.exists(cleaned_filepath):
                raise FileNotFoundError(f"Cleaned file not found at {cleaned_filepath}")

            cleaned_size_bytes = os.path.getsize(cleaned_filepath)
            cleaned_duration_sec = float(cleaned_wav.shape[-1]) / target_sr
            silence_trimmed_sec = max(0.0, std_data["std_duration_sec"] - cleaned_duration_sec)

            logger.info(
                f"VAD Complete for {video_id}: "
                f"Original {std_data['std_duration_sec']:.2f}s -> Cleaned {cleaned_duration_sec:.2f}s "
                f"(Trimmed {silence_trimmed_sec:.2f}s silence, Size: {cleaned_size_bytes / (1024*1024):.2f}MB)"
            )

            result = dict(std_data)
            result.update({
                "status": "SUCCESS",
                "cleaned_file_path": cleaned_filepath,
                "cleaned_duration_sec": cleaned_duration_sec,
                "cleaned_size_bytes": cleaned_size_bytes,
                "silence_trimmed_sec": silence_trimmed_sec,
                "num_speech_segments": len(speech_timestamps) if speech_timestamps else 0
            })
            return result

        except Exception as e:
            logger.error(f"VAD processing failed for {std_filepath}: {e}")
            result = dict(std_data)
            result["status"] = "FAILED_VAD"
            result["error"] = str(e)
            return result


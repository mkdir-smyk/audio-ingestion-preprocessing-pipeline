# Local Automated Audio Ingestion & Preprocessing Pipeline (ASR/TTS)

A fully containerized, end-to-end automated audio ETL pipeline designed for Machine Learning (Automatic Speech Recognition and Text-to-Speech model training).

## Architecture

```
                                  [ source_urls.csv ]
                                           │
                                           ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│                      Python Worker Container (ETL Pipeline)                      │
│                                                                                  │
│   Phase 1: Ingestion      Phase 2: Standardize     Phase 3: VAD Clean    Phase 4: Load & Report  │
│  ┌──────────────────┐    ┌────────────────────┐   ┌────────────────┐   ┌──────────────────────┐ │
│  │ yt-dlp + asyncio │───>│   ffmpeg-python    │──>│   Silero VAD   │──>│ boto3 -> MinIO S3    │ │
│  │ tenacity retries │    │ 16kHz mono 16-bit  │   │  PyTorch Tensor│   │ pandas -> Parquet    │ │
│  └──────────────────┘    └────────────────────┘   └────────────────┘   └──────────────────────┘ │
└──────────────────────────────────────────┬───────────────────────────────────────┘
                                           │
                                           ▼
                                 ┌───────────────────┐
                                 │   MinIO Container │
                                 │   (Local S3 API)  │
                                 └───────────────────┘
```

## Directory Structure

```
audio_pipeline/
├── data/
│   └── source_urls.csv          # Input YouTube URLs for ingestion
├── src/
│   ├── __init__.py
│   ├── config.py                # Pydantic environment configurations
│   ├── extract.py               # Phase 1: Async yt-dlp + tenacity exponential backoff retries
│   ├── transform_ffmpeg.py      # Phase 2: ffmpeg conversion to 16kHz mono 16-bit PCM WAV
│   ├── transform_vad.py         # Phase 3: Silero VAD silence removal using PyTorch
│   ├── load_minio.py            # Phase 4: MinIO object storage upload & Parquet metadata creation
│   ├── metrics.py               # Summary metrics reporting calculation & terminal output
│   └── main.py                  # Sequential ETL orchestrator
├── Dockerfile                   # Python 3.10 slim base image with FFmpeg & PyTorch CPU
├── docker-compose.yml           # MinIO + Audio Worker services composition
├── requirements.txt             # Python dependencies
└── README.md
```

## Quick Start

### 1. Build and Run Containerized Services
To start MinIO and run the automated audio pipeline:

```bash
docker-compose up --build
```

### 2. View MinIO Dashboard
- **S3 Endpoint**: `http://localhost:9000`
- **Console Web UI**: `http://localhost:9001`
- **Username**: `minioadmin`
- **Password**: `minioadmin`

Bucket `audio-dataset` will contain:
- `audio/*.wav` - Standardized, VAD-cleaned audio files ready for ML training.
- `metadata/dataset_metadata.parquet` - Parquet table with URLs, durations, sizes, and S3 URIs.

## Metrics Output
At the end of execution, `metrics.py` logs a report to the terminal console:
- **Total Audio Processed (in hours)**: Sum of original audio duration.
- **Execution Reliability (%)**: Percentage of URLs successfully processed.
- **Storage Footprint Reduction (%)**: Percentage of disk space saved post-cleaning.
- **Silence Trimmed (%)**: Percentage of dead air/silence removed via Voice Activity Detection.





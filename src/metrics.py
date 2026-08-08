import logging
from typing import List, Dict, Any

logger = logging.getLogger("audio_pipeline.metrics")

class PipelineMetrics:
    def __init__(self, processed_items: List[Dict[str, Any]], total_urls: int):
        self.processed_items = processed_items
        self.total_urls = total_urls

    def calculate_metrics(self) -> Dict[str, Any]:
        """
        Calculate pipeline execution metrics:
        1. Total Audio Processed (in hours)
        2. Execution Reliability (%)
        3. Storage Footprint Reduction (%)
        4. Silence Trimmed (%)
        """
        successful_items = [item for item in self.processed_items if item.get("status") == "SUCCESS"]
        successful_count = len(successful_items)

        # 1. Total Audio Processed (in hours) - Sum of duration of all original downloaded audio
        total_original_duration_sec = sum(item.get("original_duration_sec", 0.0) for item in self.processed_items)
        total_audio_processed_hours = total_original_duration_sec / 3600.0

        # 2. Execution Reliability (%)
        execution_reliability_pct = (successful_count / self.total_urls * 100.0) if self.total_urls > 0 else 0.0

        # 3. Storage Footprint Reduction (%)
        total_original_size_bytes = sum(item.get("original_size_bytes", 0) for item in self.processed_items)
        total_cleaned_size_bytes = sum(item.get("cleaned_size_bytes", 0) for item in successful_items)
        
        total_original_mb = total_original_size_bytes / (1024.0 * 1024.0)
        total_cleaned_mb = total_cleaned_size_bytes / (1024.0 * 1024.0)

        if total_original_size_bytes > 0:
            storage_footprint_reduction_pct = (
                (total_original_size_bytes - total_cleaned_size_bytes) / total_original_size_bytes
            ) * 100.0
        else:
            storage_footprint_reduction_pct = 0.0

        # 4. Silence Trimmed (%)
        total_silence_trimmed_sec = sum(item.get("silence_trimmed_sec", 0.0) for item in successful_items)
        
        if total_original_duration_sec > 0:
            silence_trimmed_pct = (total_silence_trimmed_sec / total_original_duration_sec) * 100.0
        else:
            silence_trimmed_pct = 0.0

        return {
            "total_urls": self.total_urls,
            "successful_urls": successful_count,
            "total_audio_processed_hours": total_audio_processed_hours,
            "total_original_duration_sec": total_original_duration_sec,
            "execution_reliability_pct": execution_reliability_pct,
            "total_original_mb": total_original_mb,
            "total_cleaned_mb": total_cleaned_mb,
            "storage_footprint_reduction_pct": storage_footprint_reduction_pct,
            "total_silence_trimmed_sec": total_silence_trimmed_sec,
            "silence_trimmed_pct": silence_trimmed_pct
        }

    def print_metrics_report(self):
        """Format and print the metrics to the console."""
        m = self.calculate_metrics()
        
        report = f"""
================================================================================
                    AUDIO PIPELINE METRICS SUMMARY
================================================================================
  - Total Audio Processed (in hours) : {m['total_audio_processed_hours']:.4f} hrs ({m['total_original_duration_sec']:.2f} seconds)
  - Execution Reliability (%)        : {m['execution_reliability_pct']:.2f}% ({m['successful_urls']}/{m['total_urls']} URLs succeeded)
  - Storage Footprint Reduction (%)  : {m['storage_footprint_reduction_pct']:.2f}% ({m['total_original_mb']:.2f} MB original -> {m['total_cleaned_mb']:.2f} MB cleaned)
  - Silence Trimmed (%)              : {m['silence_trimmed_pct']:.2f}% ({m['total_silence_trimmed_sec']:.2f} seconds of dead air removed)
================================================================================
"""
        print(report)
        logger.info("Metrics calculation and logging complete.")

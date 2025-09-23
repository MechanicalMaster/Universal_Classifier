"""Tracking utilities for metadata and progress monitoring."""

import time
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from threading import Lock

logger = logging.getLogger(__name__)


@dataclass
class ProcessingMetrics:
    """Metrics for tracking processing performance."""
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    api_calls: int = 0
    successful_pages: int = 0
    failed_pages: int = 0
    total_cost: float = 0.0
    errors: List[Dict[str, Any]] = field(default_factory=list)
    
    def add_api_call(self, cost: float = 0.0) -> None:
        """Record an API call."""
        self.api_calls += 1
        self.total_cost += cost
    
    def add_success(self) -> None:
        """Record a successful page processing."""
        self.successful_pages += 1
    
    def add_failure(self, error: Dict[str, Any]) -> None:
        """Record a failed page processing."""
        self.failed_pages += 1
        self.errors.append(error)
    
    def finish(self) -> None:
        """Mark processing as finished."""
        self.end_time = time.time()
    
    @property
    def duration(self) -> float:
        """Get processing duration in seconds."""
        end = self.end_time or time.time()
        return end - self.start_time
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        total = self.successful_pages + self.failed_pages
        if total == 0:
            return 0.0
        return (self.successful_pages / total) * 100.0


class ProgressTracker:
    """Track processing progress for multiple jobs."""
    
    def __init__(self):
        self._jobs: Dict[str, ProcessingMetrics] = {}
        self._lock = Lock()
    
    def start_job(self, job_id: str) -> ProcessingMetrics:
        """Start tracking a new job."""
        with self._lock:
            metrics = ProcessingMetrics()
            self._jobs[job_id] = metrics
            logger.info(f"Started tracking job: {job_id}")
            return metrics
    
    def get_job_metrics(self, job_id: str) -> Optional[ProcessingMetrics]:
        """Get metrics for a specific job."""
        return self._jobs.get(job_id)
    
    def finish_job(self, job_id: str) -> Optional[ProcessingMetrics]:
        """Finish tracking a job."""
        with self._lock:
            metrics = self._jobs.get(job_id)
            if metrics:
                metrics.finish()
                logger.info(f"Finished tracking job: {job_id}, duration: {metrics.duration:.2f}s")
            return metrics
    
    def cleanup_job(self, job_id: str) -> None:
        """Clean up job tracking data."""
        with self._lock:
            if job_id in self._jobs:
                del self._jobs[job_id]
                logger.info(f"Cleaned up tracking for job: {job_id}")
    
    def get_all_jobs(self) -> Dict[str, ProcessingMetrics]:
        """Get all tracked jobs."""
        return self._jobs.copy()


# Global progress tracker instance
progress_tracker = ProgressTracker()


class MetadataTracker:
    """Track metadata for files and pages during processing."""
    
    def __init__(self):
        self._metadata: Dict[str, Dict[str, Any]] = {}
        self._lock = Lock()
    
    def add_file_metadata(self, file_id: str, metadata: Dict[str, Any]) -> None:
        """Add metadata for a file."""
        with self._lock:
            self._metadata[file_id] = {
                'type': 'file',
                'timestamp': datetime.utcnow().isoformat(),
                **metadata
            }
    
    def add_page_metadata(self, page_id: str, file_id: str, page_number: int, 
                         metadata: Dict[str, Any]) -> None:
        """Add metadata for a page."""
        with self._lock:
            self._metadata[page_id] = {
                'type': 'page',
                'file_id': file_id,
                'page_number': page_number,
                'timestamp': datetime.utcnow().isoformat(),
                **metadata
            }
    
    def get_metadata(self, item_id: str) -> Optional[Dict[str, Any]]:
        """Get metadata for an item."""
        return self._metadata.get(item_id)
    
    def get_file_pages(self, file_id: str) -> List[Dict[str, Any]]:
        """Get all pages for a file."""
        pages = []
        for item_id, metadata in self._metadata.items():
            if metadata.get('type') == 'page' and metadata.get('file_id') == file_id:
                pages.append({'id': item_id, **metadata})
        
        # Sort by page number
        pages.sort(key=lambda x: x.get('page_number', 0))
        return pages
    
    def cleanup_metadata(self, prefix: str) -> None:
        """Clean up metadata with a specific prefix."""
        with self._lock:
            keys_to_remove = [k for k in self._metadata.keys() if k.startswith(prefix)]
            for key in keys_to_remove:
                del self._metadata[key]


# Global metadata tracker instance
metadata_tracker = MetadataTracker()


class RateLimitTracker:
    """Track API rate limits and usage."""
    
    def __init__(self):
        self._requests: List[float] = []
        self._lock = Lock()
        self._rate_limit = 60  # requests per minute
    
    def can_make_request(self) -> bool:
        """Check if we can make another API request."""
        with self._lock:
            current_time = time.time()
            
            # Remove requests older than 1 minute
            self._requests = [req_time for req_time in self._requests 
                            if current_time - req_time < 60]
            
            return len(self._requests) < self._rate_limit
    
    def record_request(self) -> None:
        """Record a new API request."""
        with self._lock:
            self._requests.append(time.time())
    
    def get_usage_info(self) -> Dict[str, Any]:
        """Get current usage information."""
        with self._lock:
            current_time = time.time()
            
            # Clean old requests
            self._requests = [req_time for req_time in self._requests 
                            if current_time - req_time < 60]
            
            current_usage = len(self._requests)
            remaining = max(0, self._rate_limit - current_usage)
            
            # Calculate reset time (when oldest request will be 1 minute old)
            reset_time = None
            if self._requests:
                oldest_request = min(self._requests)
                reset_time = datetime.fromtimestamp(oldest_request + 60)
            
            return {
                'rate_limit': self._rate_limit,
                'current_usage': current_usage,
                'remaining': remaining,
                'reset_time': reset_time
            }


# Global rate limit tracker instance
rate_limit_tracker = RateLimitTracker()


def estimate_openai_cost(model: str, image_count: int) -> float:
    """Estimate OpenAI API cost based on model and image count."""
    # Cost estimates (as of 2024, subject to change)
    costs = {
        'gpt-4-vision-preview': 0.01,  # per image
        'gpt-4o': 0.0075,  # per image
        'gpt-4o-mini': 0.00025,  # per image
    }
    
    base_cost = costs.get(model, 0.01)
    return base_cost * image_count

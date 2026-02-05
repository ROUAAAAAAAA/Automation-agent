
import time
import uuid
import threading
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPING = "stopping"
    STOPPED = "stopped"


@dataclass
class Job:
    job_id: str
    start_url: str
    selected_categories: List[str]
    status: JobStatus
    progress: Dict[str, Any]
    created_at: float
    updated_at: float
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    error: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    stop_requested: bool = False


class JobRegistry:
    """In-memory, thread-safe job registry (Redis-ready)."""

    def __init__(self):
        self._jobs: Dict[str, Job] = {}
        self._lock = threading.Lock()

    def create_job(self, start_url: str, selected_categories: Optional[List[str]] = None) -> str:
        with self._lock:
            job_id = str(uuid.uuid4())
            self._jobs[job_id] = Job(
                job_id=job_id,
                start_url=start_url,
                selected_categories=selected_categories or [],
                status=JobStatus.PENDING,
                progress={},
                created_at=time.time(),
                updated_at=time.time(),
            )
            return job_id

    def get_job(self, job_id: str) -> Optional[Job]:
        with self._lock:
            return self._jobs.get(job_id)

    def get_all_jobs(self) -> List[Job]:
        with self._lock:
            return list(self._jobs.values())

    def update_job(self, job_id: str, **updates) -> bool:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return False
            for k, v in updates.items():
                if hasattr(job, k):
                    setattr(job, k, v)
            job.updated_at = time.time()
            return True

    def update_progress(self, job_id: str, progress: Dict[str, Any]) -> bool:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return False
            job.progress.update(progress)
            job.updated_at = time.time()
            return True

    def mark_running(self, job_id: str) -> bool:
        return self.update_job(job_id, status=JobStatus.RUNNING, started_at=time.time())

    def mark_completed(self, job_id: str, result: Dict[str, Any]) -> bool:
        return self.update_job(
            job_id,
            status=JobStatus.COMPLETED,
            completed_at=time.time(),
            result=result,
        )

    def mark_failed(self, job_id: str, error: str) -> bool:
        return self.update_job(
            job_id,
            status=JobStatus.FAILED,
            completed_at=time.time(),
            error=error,
        )

    def request_stop(self, job_id: str) -> bool:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return False
            job.stop_requested = True
            if job.status == JobStatus.RUNNING:
                job.status = JobStatus.STOPPING
            job.updated_at = time.time()
            return True

    def should_stop(self, job_id: str) -> bool:
        with self._lock:
            job = self._jobs.get(job_id)
            return bool(job and job.stop_requested)

    def delete_job(self, job_id: str) -> bool:
        with self._lock:
            return self._jobs.pop(job_id, None) is not None


job_registry = JobRegistry()

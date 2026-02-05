
import threading
import time
import traceback
from typing import Dict, Any, Optional

from pipeline.streaming_pipeline import true_streaming_pipeline
from backend.jobs import job_registry, JobStatus


class JobStopRequested(Exception):
    """Raised when a job stop is requested."""


class PipelineWorker:
    def __init__(self):
        self._threads: Dict[str, threading.Thread] = {}
        self._lock = threading.Lock()

    def start_job(self, job_id: str, start_url: str, categories: Optional[list[str]]):
        job_registry.mark_running(job_id)

        thread = threading.Thread(
            target=self._run,
            args=(job_id, start_url, categories),
            daemon=True,
            name=f"pipeline-{job_id[:8]}"
        )

        with self._lock:
            self._threads[job_id] = thread

        thread.start()

    def stop_job(self, job_id: str):
        job_registry.request_stop(job_id)

    def _run(self, job_id: str, start_url: str, categories: Optional[list[str]]):
        def progress_cb(update: Dict[str, Any]):
            if job_registry.should_stop(job_id):
                raise JobStopRequested()
            job_registry.update_progress(job_id, update)

        try:
            result = true_streaming_pipeline(
                start_url=start_url,
                selected_categories=categories,
                progress_cb=progress_cb,
            )
            job_registry.mark_completed(job_id, result)

        except JobStopRequested:
            job_registry.update_job(
                job_id,
                status=JobStatus.STOPPED,
                completed_at=time.time(),
                error="Stopped by user",
            )

        except Exception as e:
            job_registry.mark_failed(job_id, f"{type(e).__name__}: {e}")
            traceback.print_exc()

        finally:
            with self._lock:
                self._threads.pop(job_id, None)

    def is_active(self, job_id: str) -> bool:
        with self._lock:
            t = self._threads.get(job_id)
            return bool(t and t.is_alive())

    def active_jobs(self) -> list[str]:
        with self._lock:
            return [jid for jid, t in self._threads.items() if t.is_alive()]


pipeline_worker = PipelineWorker()

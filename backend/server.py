
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dataclasses import asdict
from typing import List, Dict, Any
import time

from backend.jobs import job_registry, JobStatus
from backend.worker import pipeline_worker


class CreateJobRequest(BaseModel):
    start_url: str
    selected_categories: List[str] | None = None


app = FastAPI(title="Pipeline Orchestrator")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"service": "pipeline-orchestrator", "status": "running"}


@app.post("/jobs")
def create_job(req: CreateJobRequest):
    if not req.start_url.startswith(("http://", "https://")):
        raise HTTPException(400, "Invalid URL")

    job_id = job_registry.create_job(req.start_url, req.selected_categories)
    pipeline_worker.start_job(job_id, req.start_url, req.selected_categories)
    return {"job_id": job_id, "status": "started"}


@app.get("/jobs")
def list_jobs():
    return [asdict(j) for j in job_registry.get_all_jobs()]


@app.get("/jobs/{job_id}")
def get_job(job_id: str):
    job = job_registry.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    data = asdict(job)
    data["active"] = pipeline_worker.is_active(job_id)
    return data


@app.get("/jobs/{job_id}/status")
def job_status(job_id: str):
    job = job_registry.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return {
        "job_id": job.job_id,
        "status": job.status.value,
        "progress": job.progress,
        "updated_at": job.updated_at,
        "active": pipeline_worker.is_active(job_id),
    }


@app.post("/jobs/{job_id}/stop")
def stop_job(job_id: str):
    job = job_registry.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    pipeline_worker.stop_job(job_id)
    return {"job_id": job_id, "status": "stopping"}


@app.get("/active-jobs")
def active_jobs():
    return pipeline_worker.active_jobs()

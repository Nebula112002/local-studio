from __future__ import annotations

import asyncio
import random
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Awaitable

from .backends.base import GenerationParams, GenerationResult


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class BatchJob:
    id: str
    params: GenerationParams
    status: JobStatus = JobStatus.QUEUED
    result: GenerationResult | None = None
    error: str | None = None
    label: str = ""
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    finished_at: float | None = None


@dataclass
class BatchRequest:
    base_params: GenerationParams
    batch_count: int = 1
    seed_mode: str = "increment"  # fixed, random, increment
    prompt_variations: list[str] = field(default_factory=list)
    use_variation_suffix: bool = True


class JobQueue:
    def __init__(self) -> None:
        self._jobs: dict[str, BatchJob] = {}
        self._order: list[str] = []
        self._lock = asyncio.Lock()
        self._worker_task: asyncio.Task | None = None
        self._generate_fn: Callable[[GenerationParams], Awaitable[GenerationResult]] | None = None
        self._cancel_requested = False
        self._current_job_id: str | None = None

    def set_generator(self, fn: Callable[[GenerationParams], Awaitable[GenerationResult]]) -> None:
        self._generate_fn = fn

    async def enqueue_batch(self, request: BatchRequest) -> list[str]:
        job_ids: list[str] = []
        prompts = self._expand_prompts(request)

        async with self._lock:
            for index in range(request.batch_count):
                for prompt_index, prompt in enumerate(prompts):
                    params = GenerationParams(**vars(request.base_params))
                    params.prompt = prompt
                    params.seed = self._resolve_seed(request, index, prompt_index)

                    job_id = str(uuid.uuid4())
                    label = f"Batch {index + 1}"
                    if len(prompts) > 1:
                        label += f" - Var {prompt_index + 1}"
                    job = BatchJob(id=job_id, params=params, label=label)
                    self._jobs[job_id] = job
                    self._order.append(job_id)
                    job_ids.append(job_id)

        self._ensure_worker()
        return job_ids

    def _expand_prompts(self, request: BatchRequest) -> list[str]:
        base = request.base_params.prompt.strip()
        if not request.prompt_variations:
            return [base]
        prompts = [base]
        for variation in request.prompt_variations:
            variation = variation.strip()
            if not variation:
                continue
            if request.use_variation_suffix:
                prompts.append(f"{base}, {variation}")
            else:
                prompts.append(variation)
        return prompts

    def _resolve_seed(self, request: BatchRequest, batch_index: int, prompt_index: int) -> int:
        base_seed = request.base_params.seed
        offset = batch_index * max(1, len(self._expand_prompts(request))) + prompt_index

        if request.seed_mode == "random" or base_seed < 0:
            return random.randint(0, 2**32 - 1)
        if request.seed_mode == "increment":
            return base_seed + offset
        return base_seed

    def _ensure_worker(self) -> None:
        if self._worker_task is None or self._worker_task.done():
            self._worker_task = asyncio.create_task(self._worker())

    async def _worker(self) -> None:
        while True:
            job_id = await self._next_queued()
            if job_id is None:
                break
            if self._cancel_requested:
                self._jobs[job_id].status = JobStatus.CANCELLED
                continue

            job = self._jobs[job_id]
            job.status = JobStatus.RUNNING
            job.started_at = time.time()
            self._current_job_id = job_id

            try:
                if self._generate_fn is None:
                    raise RuntimeError("No generator configured")
                job.result = await self._generate_fn(job.params)
                job.status = JobStatus.COMPLETED
            except Exception as exc:
                job.status = JobStatus.FAILED
                job.error = str(exc)
            finally:
                job.finished_at = time.time()
                self._current_job_id = None

    async def _next_queued(self) -> str | None:
        async with self._lock:
            for job_id in self._order:
                if self._jobs[job_id].status == JobStatus.QUEUED:
                    return job_id
        return None

    def get_job(self, job_id: str) -> BatchJob | None:
        return self._jobs.get(job_id)

    def list_jobs(self) -> list[dict[str, Any]]:
        return [self.serialize_job(job) for job in self._jobs.values()]

    def serialize_job(self, job: BatchJob) -> dict[str, Any]:
        return self._serialize_job(job)

    def get_queue_status(self) -> dict[str, Any]:
        jobs = list(self._jobs.values())
        return {
            "total": len(jobs),
            "queued": sum(1 for j in jobs if j.status == JobStatus.QUEUED),
            "running": sum(1 for j in jobs if j.status == JobStatus.RUNNING),
            "completed": sum(1 for j in jobs if j.status == JobStatus.COMPLETED),
            "failed": sum(1 for j in jobs if j.status == JobStatus.FAILED),
            "current_job_id": self._current_job_id,
        }

    def cancel_queue(self) -> None:
        self._cancel_requested = True
        for job_id in self._order:
            job = self._jobs[job_id]
            if job.status == JobStatus.QUEUED:
                job.status = JobStatus.CANCELLED

    def clear_completed(self) -> None:
        to_remove = [jid for jid, job in self._jobs.items() if job.status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED)]
        for jid in to_remove:
            del self._jobs[jid]
            if jid in self._order:
                self._order.remove(jid)

    def _serialize_job(self, job: BatchJob) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": job.id,
            "status": job.status.value,
            "label": job.label,
            "prompt": job.params.prompt,
            "negative_prompt": job.params.negative_prompt,
            "width": job.params.width,
            "height": job.params.height,
            "steps": job.params.steps,
            "cfg_scale": job.params.cfg_scale,
            "sampler": job.params.sampler,
            "scheduler": job.params.scheduler,
            "seed": job.params.seed,
            "batch_size": job.params.batch_size,
            "created_at": job.created_at,
            "started_at": job.started_at,
            "finished_at": job.finished_at,
            "error": job.error,
        }
        if job.result:
            payload["images"] = job.result.images
            payload["videos"] = job.result.videos
            payload["seeds"] = job.result.seeds
            payload["mode"] = job.params.mode
        return payload

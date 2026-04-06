"""
External Compute Queue
========================
Lightweight queue for offloading heavy ML training and Monte Carlo
simulations to external GPU clusters.

Supported backends:
  1. RunPod (serverless GPU endpoints)
  2. Local CPU fallback (always available)

Keeps real-time inference lightweight on the primary server.
Training jobs are dispatched async and results polled.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional

import httpx
import structlog

log = structlog.get_logger(__name__)

JOB_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "jobs"
JOB_DIR.mkdir(parents=True, exist_ok=True)


class ComputeBackend(str, Enum):
    LOCAL = "local"
    RUNPOD = "runpod"
    TRUEFOUNDRY = "truefoundry"
    NORTHFLANK = "northflank"


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ComputeJob:
    """A queued compute job."""
    id: str
    job_type: str  # "retrain", "monte_carlo", "backtest"
    backend: ComputeBackend
    status: JobStatus = JobStatus.QUEUED
    created_at: dt.datetime = field(default_factory=lambda: dt.datetime.now(dt.UTC))
    started_at: Optional[dt.datetime] = None
    completed_at: Optional[dt.datetime] = None
    payload: dict = field(default_factory=dict)
    result: Optional[dict] = None
    error: Optional[str] = None
    remote_job_id: Optional[str] = None


class ComputeQueue:
    """
    Manages offloading of heavy compute to external services.

    Usage:
        queue = ComputeQueue(backend="runpod", api_key="...")
        job = await queue.submit_retrain(training_data)
        result = await queue.wait_for_result(job.id)
    """

    def __init__(
        self,
        backend: str = "local",
        api_key: str = "",
        endpoint_url: str = "",
    ) -> None:
        self.backend = ComputeBackend(backend)
        self._api_key = api_key
        self._endpoint_url = endpoint_url
        self._client = httpx.AsyncClient(timeout=120.0)
        self._jobs: dict[str, ComputeJob] = {}

    async def submit_retrain(
        self,
        price_history: list[dict],
        feature_history: list[dict],
    ) -> ComputeJob:
        """Submit a model retraining job."""
        job_id = f"retrain_{dt.datetime.now(dt.UTC).strftime('%Y%m%d_%H%M%S')}"
        payload = {
            "price_history": price_history,
            "feature_history": feature_history,
        }

        job = ComputeJob(
            id=job_id,
            job_type="retrain",
            backend=self.backend,
            payload=payload,
        )
        self._jobs[job_id] = job

        if self.backend == ComputeBackend.LOCAL:
            # Run locally in background
            asyncio.create_task(self._run_local_retrain(job))
        elif self.backend == ComputeBackend.RUNPOD:
            await self._submit_runpod(job)
        else:
            # Fallback to local
            asyncio.create_task(self._run_local_retrain(job))

        log.info("compute.submitted", job_id=job_id, backend=self.backend.value)
        return job

    async def submit_monte_carlo(
        self,
        params: dict,
        n_scenarios: int = 10000,
    ) -> ComputeJob:
        """Submit a Monte Carlo simulation job."""
        job_id = f"mc_{dt.datetime.now(dt.UTC).strftime('%Y%m%d_%H%M%S')}"
        payload = {**params, "n_scenarios": n_scenarios}

        job = ComputeJob(
            id=job_id,
            job_type="monte_carlo",
            backend=self.backend,
            payload=payload,
        )
        self._jobs[job_id] = job

        if self.backend == ComputeBackend.LOCAL:
            asyncio.create_task(self._run_local_monte_carlo(job))
        elif self.backend == ComputeBackend.RUNPOD:
            await self._submit_runpod(job)
        else:
            asyncio.create_task(self._run_local_monte_carlo(job))

        return job

    async def get_job_status(self, job_id: str) -> Optional[ComputeJob]:
        """Check job status. For remote backends, polls the API."""
        job = self._jobs.get(job_id)
        if not job:
            return None

        if (
            job.backend == ComputeBackend.RUNPOD
            and job.status == JobStatus.RUNNING
            and job.remote_job_id
        ):
            await self._poll_runpod(job)

        return job

    async def wait_for_result(
        self, job_id: str, timeout_seconds: int = 600
    ) -> Optional[dict]:
        """Wait for a job to complete and return its result."""
        deadline = dt.datetime.now(dt.UTC) + dt.timedelta(seconds=timeout_seconds)
        while dt.datetime.now(dt.UTC) < deadline:
            job = await self.get_job_status(job_id)
            if not job:
                return None
            if job.status == JobStatus.COMPLETED:
                return job.result
            if job.status == JobStatus.FAILED:
                return {"error": job.error}
            await asyncio.sleep(2)
        return {"error": "timeout"}

    # ── Local execution ─────────────────────────────────────

    async def _run_local_retrain(self, job: ComputeJob) -> None:
        """Run retraining locally on CPU."""
        job.status = JobStatus.RUNNING
        job.started_at = dt.datetime.now(dt.UTC)

        try:
            from core.market.price_ml import price_ensemble
            result = await price_ensemble.retrain(
                job.payload["price_history"],
                job.payload["feature_history"],
            )
            job.result = result
            job.status = JobStatus.COMPLETED
        except Exception as e:
            job.error = str(e)[:500]
            job.status = JobStatus.FAILED
            log.error("compute.local_retrain_failed", error=job.error)
        finally:
            job.completed_at = dt.datetime.now(dt.UTC)

    async def _run_local_monte_carlo(self, job: ComputeJob) -> None:
        """Run Monte Carlo simulation locally."""
        job.status = JobStatus.RUNNING
        job.started_at = dt.datetime.now(dt.UTC)

        try:
            import numpy as np
            params = job.payload
            n = params.get("n_scenarios", 10000)
            spot = params.get("spot", 75.0)
            horizon = params.get("horizon_weeks", 4)
            weekly_vol = spot * 0.04

            rng = np.random.default_rng()
            # GBM-like simulation with jumps
            scenarios = []
            for _ in range(n):
                price = spot
                for w in range(horizon):
                    ret = rng.normal(0, weekly_vol / spot)
                    # 3% chance of ±10% jump per week
                    if rng.random() < 0.03:
                        ret += rng.choice([-1, 1]) * 0.10
                    price *= (1 + ret)
                scenarios.append(price)

            scenarios = np.array(scenarios)
            job.result = {
                "n_scenarios": n,
                "p5": round(float(np.percentile(scenarios, 5)), 1),
                "p10": round(float(np.percentile(scenarios, 10)), 1),
                "p25": round(float(np.percentile(scenarios, 25)), 1),
                "p50": round(float(np.percentile(scenarios, 50)), 1),
                "p75": round(float(np.percentile(scenarios, 75)), 1),
                "p90": round(float(np.percentile(scenarios, 90)), 1),
                "p95": round(float(np.percentile(scenarios, 95)), 1),
                "mean": round(float(np.mean(scenarios)), 1),
                "std": round(float(np.std(scenarios)), 1),
                "prob_above_spot": round(float(np.mean(scenarios > spot)), 3),
            }
            job.status = JobStatus.COMPLETED
        except Exception as e:
            job.error = str(e)[:500]
            job.status = JobStatus.FAILED
        finally:
            job.completed_at = dt.datetime.now(dt.UTC)

    # ── RunPod execution ────────────────────────────────────

    async def _submit_runpod(self, job: ComputeJob) -> None:
        """Submit job to RunPod serverless endpoint."""
        if not self._api_key or not self._endpoint_url:
            log.warning("compute.runpod_no_credentials, falling back to local")
            asyncio.create_task(self._run_local_retrain(job)
                                if job.job_type == "retrain"
                                else self._run_local_monte_carlo(job))
            return

        try:
            resp = await self._client.post(
                f"{self._endpoint_url}/run",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={"input": job.payload},
            )
            if resp.status_code == 200:
                data = resp.json()
                job.remote_job_id = data.get("id")
                job.status = JobStatus.RUNNING
                job.started_at = dt.datetime.now(dt.UTC)
            else:
                log.warning("compute.runpod_submit_failed", status=resp.status_code)
                # Fallback to local
                asyncio.create_task(self._run_local_retrain(job))
        except Exception as e:
            log.warning("compute.runpod_error", error=str(e)[:100])
            asyncio.create_task(self._run_local_retrain(job))

    async def _poll_runpod(self, job: ComputeJob) -> None:
        """Poll RunPod for job completion."""
        if not job.remote_job_id:
            return
        try:
            resp = await self._client.get(
                f"{self._endpoint_url}/status/{job.remote_job_id}",
                headers={"Authorization": f"Bearer {self._api_key}"},
            )
            if resp.status_code == 200:
                data = resp.json()
                status = data.get("status")
                if status == "COMPLETED":
                    job.result = data.get("output", {})
                    job.status = JobStatus.COMPLETED
                    job.completed_at = dt.datetime.now(dt.UTC)
                elif status == "FAILED":
                    job.error = data.get("error", "Unknown error")
                    job.status = JobStatus.FAILED
                    job.completed_at = dt.datetime.now(dt.UTC)
        except Exception:
            pass

    def get_all_jobs(self) -> list[dict]:
        """Return all job statuses."""
        return [
            {
                "id": j.id,
                "type": j.job_type,
                "backend": j.backend.value,
                "status": j.status.value,
                "created_at": j.created_at.isoformat(),
                "completed_at": j.completed_at.isoformat() if j.completed_at else None,
            }
            for j in self._jobs.values()
        ]

    async def close(self) -> None:
        await self._client.aclose()


# Factory
def create_compute_queue() -> ComputeQueue:
    """Create compute queue from settings."""
    from config.settings import settings
    backend = getattr(settings, "compute_backend", "local")
    api_key = getattr(settings, "compute_api_key", "")
    endpoint = getattr(settings, "compute_endpoint_url", "")
    return ComputeQueue(backend=backend, api_key=api_key, endpoint_url=endpoint)

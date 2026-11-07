"""Test-only, bounded in-memory observations; no lease decisions are changed."""

import asyncio
import hashlib
import json
from datetime import UTC, datetime

from core.scheduler.persistence import SchedulerPersistence


def _claim_ref(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:16]


class SchedulerTimeline:
    def __init__(self, limit=20000):
        self.events = []
        self.limit = limit
        self.dropped = 0

    def record(self, event, **fields):
        if len(self.events) >= self.limit:
            self.dropped += 1
            return
        self.events.append({
            "event": event,
            "monotonic": asyncio.get_running_loop().time(),
            "utc": datetime.now(UTC).isoformat(),
            **fields,
        })

    def save(self, path):
        path.write_text(json.dumps({
            "schema_version": 1,
            "boundary": "ISOLATED_SYNTHETIC_OBSERVATION_NOT_ROOT_CAUSE_PROOF",
            "dropped": self.dropped,
            "events": self.events,
        }, indent=2), encoding="utf-8")


class TimelinePersistence(SchedulerPersistence):
    def __init__(self, path, timeline, instance):
        super().__init__(str(path))
        self.timeline = timeline
        self.instance = instance

    def _record(self, event, **fields):
        self.timeline.record(event, instance=self.instance, **fields)

    async def claim_job(self, job_id, **kwargs):
        self._record("claim.begin", job_id=job_id,
                     run_id=kwargs["run_id"], claim_ref=_claim_ref(kwargs["claim_token"]),
                     request_now=kwargs["now"].isoformat(),
                     requested_expiry=kwargs["claim_expires_at"].isoformat())
        try:
            result = await super().claim_job(job_id, **kwargs)
        except Exception as exc:
            self._record("claim.error", job_id=job_id, error_type=type(exc).__name__)
            raise
        self._record("claim.end", job_id=job_id, accepted=result is not None)
        return result

    async def renew_claim(self, job_id, claim_token, claim_expires_at, **kwargs):
        self._record("renew.begin", job_id=job_id,
                     claim_ref=_claim_ref(claim_token),
                     requested_expiry=claim_expires_at.isoformat())
        try:
            result = await super().renew_claim(job_id, claim_token, claim_expires_at, **kwargs)
        except Exception as exc:
            self._record("renew.error", job_id=job_id, error_type=type(exc).__name__)
            raise
        self._record("renew.end", job_id=job_id,
                     claim_ref=_claim_ref(claim_token), renewed=result)
        return result

    async def release_expired_claims(self, now, **kwargs):
        self._record("release.begin", request_now=now.isoformat())
        try:
            result = await super().release_expired_claims(now, **kwargs)
        except Exception as exc:
            self._record("release.error", error_type=type(exc).__name__)
            raise
        self._record("release.end", released=result)
        return result

    async def finalize_claim(self, job, run, claim_token):
        self._record("finalize.begin", job_id=job.info.id, run_id=run.id,
                     claim_ref=_claim_ref(claim_token))
        try:
            result = await super().finalize_claim(job, run, claim_token)
        except Exception as exc:
            self._record("finalize.error", job_id=job.info.id,
                         run_id=run.id, error_type=type(exc).__name__)
            raise
        self._record("finalize.end", job_id=job.info.id, run_id=run.id)
        return result

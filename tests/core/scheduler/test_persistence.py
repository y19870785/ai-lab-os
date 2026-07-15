import os

import pytest

from core.scheduler.persistence import SchedulerPersistence
from core.scheduler.exceptions import SchedulerPersistenceError
from core.scheduler.models import Job, JobInfo, Trigger, TriggerType


pytestmark = pytest.mark.asyncio(loop_scope="function")


class TestSchedulerPersistence:
    DB_PATH = "test_scheduler.db"

    async def test_save_and_load(self):
        p = SchedulerPersistence(self.DB_PATH)
        await p.initialize()
        try:
            job = Job(info=JobInfo(name="test-persist"), workflow_name="test-wf",
                      trigger=Trigger(trigger_type=TriggerType.INTERVAL, interval_seconds=60))
            await p.save_job(job)
            jobs = await p.load_jobs()
            assert len(jobs) == 1
            assert jobs[0].info.name == "test-persist"
        finally:
            await p.close()
            if os.path.exists(self.DB_PATH):
                os.remove(self.DB_PATH)

    async def test_delete(self):
        p = SchedulerPersistence(self.DB_PATH)
        await p.initialize()
        try:
            job = Job(info=JobInfo(name="to-delete"))
            await p.save_job(job)
            assert await p.delete_job(job.info.id) is True
            assert await p.delete_job(job.info.id) is False
        finally:
            await p.close()
            if os.path.exists(self.DB_PATH):
                os.remove(self.DB_PATH)

    async def test_load_empty(self):
        p = SchedulerPersistence(self.DB_PATH)
        await p.initialize()
        try:
            jobs = await p.load_jobs()
            assert jobs == []
        finally:
            await p.close()
            if os.path.exists(self.DB_PATH):
                os.remove(self.DB_PATH)

    async def test_save_existing_rejects_unconditional_overwrite(self):
        p = SchedulerPersistence(self.DB_PATH)
        await p.initialize()
        try:
            job = Job(info=JobInfo(name="update-me"), workflow_name="wf1")
            await p.save_job(job)
            job.workflow_name = "wf2"
            with pytest.raises(SchedulerPersistenceError):
                await p.save_job(job)
            jobs = await p.load_jobs()
            assert len(jobs) == 1
            assert jobs[0].workflow_name == "wf1"
        finally:
            await p.close()
            if os.path.exists(self.DB_PATH):
                os.remove(self.DB_PATH)

import pytest
pytestmark = pytest.mark.asyncio(loop_scope="function")
import os
from core.scheduler.persistence import SchedulerPersistence
from core.scheduler.models import Job, JobInfo, Trigger, TriggerType


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

    async def test_update_existing(self):
        p = SchedulerPersistence(self.DB_PATH)
        await p.initialize()
        try:
            job = Job(info=JobInfo(name="update-me"), workflow_name="wf1")
            await p.save_job(job)
            job.workflow_name = "wf2"
            await p.save_job(job)
            jobs = await p.load_jobs()
            assert len(jobs) == 1
            assert jobs[0].workflow_name == "wf2"
        finally:
            await p.close()
            if os.path.exists(self.DB_PATH):
                os.remove(self.DB_PATH)

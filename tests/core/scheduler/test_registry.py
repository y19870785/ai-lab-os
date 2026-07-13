import pytest
from core.scheduler.registry import SchedulerRegistry
from core.scheduler.models import Job, JobInfo
from core.scheduler.exceptions import JobNotFoundError, JobAlreadyExistsError


class TestSchedulerRegistry:
    def _make_job(self, name="test-job", tags=None):
        return Job(info=JobInfo(name=name, tags=tags or []))

    def test_register_and_get(self):
        reg = SchedulerRegistry()
        job = self._make_job("j1")
        reg.register(job)
        assert reg.exists(job.info.id)
        assert reg.get(job.info.id).info.name == "j1"

    def test_duplicate_register(self):
        reg = SchedulerRegistry()
        reg.register(self._make_job("j1"))
        with pytest.raises(JobAlreadyExistsError):
            reg.register(self._make_job("j1"))

    def test_unregister(self):
        reg = SchedulerRegistry()
        job = self._make_job("temp")
        reg.register(job)
        assert reg.unregister(job.info.id) is True
        assert reg.unregister(job.info.id) is False

    def test_get_nonexistent(self):
        reg = SchedulerRegistry()
        with pytest.raises(JobNotFoundError):
            reg.get("nope")

    def test_get_by_name(self):
        reg = SchedulerRegistry()
        job = self._make_job("hello")
        reg.register(job)
        found = reg.get_by_name("hello")
        assert found is not None
        assert found.info.name == "hello"

    def test_get_by_name_not_found(self):
        reg = SchedulerRegistry()
        assert reg.get_by_name("nope") is None

    def test_list(self):
        reg = SchedulerRegistry()
        reg.register(self._make_job("a"))
        reg.register(self._make_job("b"))
        assert reg.count == 2
        assert len(reg.list()) == 2

    def test_search_by_tag(self):
        reg = SchedulerRegistry()
        reg.register(self._make_job("a", tags=["fast"]))
        reg.register(self._make_job("b", tags=["slow"]))
        results = reg.search(tag="fast")
        assert len(results) == 1
        assert results[0].info.name == "a"

    def test_search_by_name(self):
        reg = SchedulerRegistry()
        reg.register(self._make_job("daily-report"))
        reg.register(self._make_job("weekly-digest"))
        results = reg.search(name_pattern="daily")
        assert len(results) == 1

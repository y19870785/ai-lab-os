"""Application Registry。"""
from applications.models import ApplicationInfo, ApplicationManifest, ApplicationStatus
from applications.exceptions import ApplicationNotFoundError

class ApplicationRegistry:
    def __init__(self):
        self._apps: dict[str, ApplicationInfo] = {}
        self._manifests: dict[str, ApplicationManifest] = {}
        self._instances: dict[str, object] = {}

    def register(self, info: ApplicationInfo, manifest: ApplicationManifest, instance=None) -> None:
        self._apps[info.application_id] = info
        self._manifests[info.application_id] = manifest
        if instance:
            self._instances[info.application_id] = instance

    def unregister(self, app_id: str) -> bool:
        self._manifests.pop(app_id, None)
        self._instances.pop(app_id, None)
        return self._apps.pop(app_id, None) is not None

    def get(self, app_id: str) -> ApplicationInfo:
        if app_id not in self._apps:
            raise ApplicationNotFoundError(app_id)
        return self._apps[app_id]

    def get_manifest(self, app_id: str) -> ApplicationManifest:
        if app_id not in self._manifests:
            raise ApplicationNotFoundError(app_id)
        return self._manifests[app_id]

    def find_by_name(self, name: str) -> list[ApplicationInfo]:
        return [a for a in self._apps.values() if a.name == name]

    def list(self) -> list[ApplicationInfo]:
        return list(self._apps.values())

    def set_status(self, app_id: str, status: ApplicationStatus) -> None:
        self.get(app_id).status = status

    @property
    def count(self) -> int:
        return len(self._apps)

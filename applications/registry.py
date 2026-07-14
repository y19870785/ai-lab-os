"""Application Registry。"""
from applications.models import ApplicationInfo, ApplicationManifest, ApplicationStatus
from applications.exceptions import ApplicationAlreadyRegisteredError, ApplicationNotFoundError

class ApplicationRegistry:
    def __init__(self):
        self._apps: dict[str, ApplicationInfo] = {}
        self._manifests: dict[str, ApplicationManifest] = {}
        self._instances: dict[str, object] = {}
        self._ids_by_name: dict[str, str] = {}

    def register(self, info: ApplicationInfo, manifest: ApplicationManifest, instance=None) -> None:
        if info.name in self._ids_by_name:
            raise ApplicationAlreadyRegisteredError(info.name)
        self._apps[info.application_id] = info
        self._manifests[info.application_id] = manifest
        self._ids_by_name[info.name] = info.application_id
        if instance is not None:
            self._instances[info.application_id] = instance

    def unregister(self, app_id: str) -> bool:
        info = self._apps.get(app_id)
        if info is not None:
            self._ids_by_name.pop(info.name, None)
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
        info = self.get_info_by_name(name)
        return [info] if info is not None else []

    def get_info_by_name(self, name: str) -> ApplicationInfo | None:
        app_id = self._ids_by_name.get(name)
        return self._apps.get(app_id) if app_id else None

    def get_manifest_by_name(self, name: str) -> ApplicationManifest | None:
        app_id = self._ids_by_name.get(name)
        return self._manifests.get(app_id) if app_id else None

    def get_instance_by_name(self, name: str) -> object | None:
        app_id = self._ids_by_name.get(name)
        return self._instances.get(app_id) if app_id else None

    def list(self) -> list[ApplicationInfo]:
        return list(self._apps.values())

    def set_status(self, app_id: str, status: ApplicationStatus) -> None:
        self.get(app_id).status = status

    @property
    def count(self) -> int:
        return len(self._apps)

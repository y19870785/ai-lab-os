"""Applications route。"""
from fastapi import APIRouter, Depends
from api.dependencies import get_system
from api.models import AppInfo
from core.system.container import SystemContainer

router = APIRouter(prefix="/applications", tags=["applications"])

@router.get("", response_model=list[AppInfo])
async def list_apps(system: SystemContainer = Depends(get_system)):
    apps = await system.application_runtime.list_applications()
    return [AppInfo(application_id=a.application_id, name=a.name, version=a.version, status=a.status.value) for a in apps]

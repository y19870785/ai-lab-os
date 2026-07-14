"""Applications route。"""
from fastapi import APIRouter, Depends
from api.dependencies import get_runtime
from api.models import AppInfo
from applications.runtime import ApplicationRuntime

router = APIRouter(prefix="/applications", tags=["applications"])

@router.get("", response_model=list[AppInfo])
async def list_apps(runtime: ApplicationRuntime = Depends(get_runtime)):
    apps = await runtime.list_applications()
    return [AppInfo(application_id=a.application_id, name=a.name, version=a.version, status=a.status.value) for a in apps]

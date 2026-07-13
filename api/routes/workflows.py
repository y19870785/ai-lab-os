"""Workflows route。"""
from fastapi import APIRouter
router = APIRouter(prefix="/workflows", tags=["workflows"])

@router.post("/{name}/run")
async def run_workflow(name: str):
    return {"workflow": name, "status": "started"}

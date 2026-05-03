from fastapi import APIRouter
from services.report_service import generate_report

router = APIRouter(prefix="/report", tags=["report"])


@router.get("/{workspace_id}")
def get_report(workspace_id: str):
    return generate_report(workspace_id)

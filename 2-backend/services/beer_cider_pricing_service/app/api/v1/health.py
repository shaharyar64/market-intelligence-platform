from fastapi import APIRouter


router = APIRouter(tags=["beer health"])


@router.get("/health")
async def health():
    return {"success": True, "data": {"status": "ok"}}

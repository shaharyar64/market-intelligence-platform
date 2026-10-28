from fastapi import APIRouter


router = APIRouter(tags=["horeca health"])


@router.get("/health")
async def health():
    return {"status": "ok"}
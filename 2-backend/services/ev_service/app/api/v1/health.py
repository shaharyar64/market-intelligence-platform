from fastapi import APIRouter


router = APIRouter(tags=["EV Health"])


@router.get("/health")
async def health():
    return {"status": "ok"}
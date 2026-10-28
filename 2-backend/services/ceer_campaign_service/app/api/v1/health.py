from fastapi import APIRouter


router = APIRouter(tags=["CEER Campaign Health"])


@router.get("/health")
async def health():
    return {"status": "ok", "service": "ceer_campaign"}

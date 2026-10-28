from fastapi import APIRouter


router = APIRouter(tags=["bank spatial health"])


@router.get("/health")
async def health():
    return {"status": "ok"}
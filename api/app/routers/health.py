from fastapi import APIRouter

router = APIRouter(tags=["infra"])


@router.get("/health")
def health() -> dict[str, str]:
    """Sonda de liveness usada pelo compose e pelo CI."""
    return {"status": "ok"}

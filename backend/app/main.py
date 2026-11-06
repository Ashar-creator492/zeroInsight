from fastapi import FastAPI

from backend.app.routers.products import router as products_router

app = FastAPI(title="ZeroInsight AI", version="0.1.0")
app.include_router(products_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

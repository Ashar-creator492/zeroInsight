from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.routers.products import router as products_router
from backend.app.routers.intelligence import router as intelligence_router

from backend.app.routers.retrieval import router as retrieval_router
from backend.app.routers.chat import router as chat_router

app = FastAPI(title="ZeroInsight AI", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
                   allow_methods=["GET", "POST"], allow_headers=["*"])
app.include_router(products_router)
app.include_router(intelligence_router)
app.include_router(retrieval_router)
app.include_router(chat_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

"""Local whole-review embeddings and PostgreSQL similarity retrieval."""
from functools import lru_cache

from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.config import get_settings


@lru_cache(maxsize=1)
def embeddings():
    return HuggingFaceEmbeddings(model_name=get_settings().embedding_model, cache_folder=".cache/huggingface/hub")


def index_reviews(db: Session, batch_size: int = 32) -> dict[str, int]:
    model = get_settings().embedding_model
    total = 0
    while True:
        rows = db.execute(text("""
            SELECT r.id, r.review_text, r.content_fingerprint
            FROM reviews r LEFT JOIN review_embeddings e
              ON e.review_id = r.id AND e.model_name = :model
            WHERE r.product_id = 'luna-smartwatch'
              AND (e.review_id IS NULL OR e.content_fingerprint <> r.content_fingerprint)
            ORDER BY r.id LIMIT :batch_size
        """), {"model": model, "batch_size": batch_size}).mappings().all()
        if not rows:
            break
        documents = [Document(page_content=row.review_text, metadata={"review_id": row.id}) for row in rows]
        vectors = embeddings().embed_documents([doc.page_content for doc in documents])
        if len(vectors) != len(rows) or any(len(vector) != 384 for vector in vectors):
            raise ValueError("Embedding model must return one 384-dimensional vector per review")
        for row, vector in zip(rows, vectors):
            db.execute(text("""
                INSERT INTO review_embeddings (review_id, model_name, content_fingerprint, embedding)
                VALUES (:id, :model, :fingerprint, CAST(:embedding AS vector))
                ON CONFLICT (review_id, model_name) DO UPDATE SET
                  content_fingerprint = EXCLUDED.content_fingerprint, embedding = EXCLUDED.embedding
            """), {"id": row.id, "model": model, "fingerprint": row.content_fingerprint,
                   "embedding": str(vector)})
        db.commit()
        total += len(rows)
        print(f"Indexed {total} reviews in this run", flush=True)
    return {"indexed": total}


def retrieve_reviews(db: Session, question: str, product_id: str = "luna-smartwatch",
                     rating: int | None = None, limit: int = 5) -> list[dict]:
    vector = embeddings().embed_query(question)
    if len(vector) != 384:
        raise ValueError("Embedding model must return 384-dimensional vectors")
    rows = db.execute(text("""
        SELECT r.id, r.source_id, r.product_id, r.review_text, r.title, r.rating,
               r.review_date, r.source_url, 1 - (e.embedding <=> CAST(:embedding AS vector)) AS similarity
        FROM review_embeddings e JOIN reviews r ON r.id = e.review_id
        WHERE e.model_name = :model AND e.content_fingerprint = r.content_fingerprint
          AND r.product_id = :product_id AND (CAST(:rating AS integer) IS NULL OR r.rating = CAST(:rating AS integer))
        ORDER BY e.embedding <=> CAST(:embedding AS vector), r.id
        LIMIT :limit
    """), {"model": get_settings().embedding_model, "embedding": str(vector),
           "product_id": product_id, "rating": rating, "limit": limit}).mappings().all()
    return [dict(row) for row in rows]

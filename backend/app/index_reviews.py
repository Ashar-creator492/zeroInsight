# Command-line entry point for indexing review embeddings.
"""Index Luna reviews locally; safe to interrupt and rerun."""
from sqlalchemy.orm import Session
from backend.app.database import make_engine
from backend.app.services.retrieval import index_reviews

if __name__ == "__main__":
    with Session(make_engine()) as db:
        print(index_reviews(db))

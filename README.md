# ZeroInsight AI

Independent portfolio project inspired by Zero Lifestyle. The backend analyzes the supplied **Luna Smartwatch** reviews only. Phase 2 adds optional Groq classification; it does not include embeddings, a dashboard, or other products.

## Structure

- `backend/app/`: FastAPI, SQLAlchemy models, configuration, and CSV ingestion
- `backend/migrations/`: Alembic schema migration
- `tests/`: ingestion and API tests
- `data/raw/`: local review CSV, ignored by Git

## Local setup

Requires Python 3.10+ and a running PostgreSQL server. On macOS with Homebrew, run `brew install postgresql@17`, `brew services start postgresql@17`, and `/opt/homebrew/opt/postgresql@17/bin/createdb zeroinsight`. For this local setup, set `DATABASE_URL=postgresql+psycopg:///zeroinsight` in `.env`. For another PostgreSQL installation, use its actual connection string and a user with permission to create tables.

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit DATABASE_URL in .env; keep .env private.
mkdir -p data/raw
cp /path/to/luna_510_reviews.csv data/raw/luna_510_reviews.csv
python -m backend.app.ingest data/raw/luna_510_reviews.csv --dry-run
alembic upgrade head
python -m backend.app.ingest data/raw/luna_510_reviews.csv
uvicorn backend.app.main:app --reload
```

The import command validates the whole file before writing and prints a data quality report with inserted, updated, and unchanged counts. Re-running it skips unchanged reviews. Invalid dates are preserved as raw strings with a null parsed date. Malformed rows, invalid ratings, missing required values, duplicate source IDs, and unexpected product names stop the import.

API: `/health`, `/api/products`, `/api/products/luna-smartwatch/reviews?page=1&page_size=20`, `/api/products/luna-smartwatch/summary`. Open `/docs` for the interactive API reference.

## Phase 2 review intelligence

Set `GROQ_API_KEY` in your private `.env` and optionally change `GROQ_MODEL` (default `openai/gpt-oss-20b`). The backend and Phase 1 endpoints run without a key. Apply `alembic upgrade head`, then run a ten-review pilot with `python -m backend.app.classify`. This selects a stable mix of real Luna ratings and prints original text alongside interpretations for manual review. Re-running skips completed results for unchanged review content. Failed records can be retried. Each review commits separately, so interruption is resumable. API token counts are stored when Groq returns usage metadata.

After approving the pilot, an explicit `python -m backend.app.classify --all --limit 25` processes up to 25 pending or failed Luna reviews; repeat for later batches. No full batch is started automatically. A model or classification version change produces separate results. Changed review content is reclassified while old review text remains in the review table.

Intelligence API: `/api/products/luna-smartwatch/intelligence/progress`, `/sentiment`, `/complaints`, `/praised-features`, and `/classifications?page=1&page_size=20`. Counts include only completed, current classifications. Progress reports analyzed, failed, and pending separately. Category and feature labels are AI interpretations of customer reports, not confirmed defects.

## Tests

```sh
python -m pytest -q
```

Tests use an in-memory SQLite database for isolated checks; the running application uses the configured PostgreSQL URL. PostgreSQL integration requires a local server and is not silently replaced by SQLite.

## Dataset inspection

The supplied CSV has 510 records and columns `id`, `product`, `review_text`, `title`, `rating`, `date`, and `source_url`. All records name Luna Smartwatch. There are 253 empty titles, no other missing fields, no duplicate IDs, no invalid ratings, and no malformed rows. All dates parse as `MM/DD/YYYY`; the range is 2023-12-17 through 2026-11-05. There are 213 repeated review texts, which remain separate source records. Review text lengths range from 1 to 290 characters. Ratings: 5★ 411, 4★ 78, 3★ 18, 2★ 1, 1★ 2. The raw file is ignored by Git pending redistribution rights.

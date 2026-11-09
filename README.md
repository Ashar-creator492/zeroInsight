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

## Phase 3 local preview

The landing page is the first frontend milestone. It uses React, TypeScript, Vite, and Tailwind. From the project root:

```sh
cd frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173/` for the landing page or `http://127.0.0.1:5173/dashboard` for the Overview. The analytics pages are `/dashboard/reviews`, `/dashboard/sentiment`, and `/dashboard/complaints`. Start PostgreSQL and FastAPI in a second terminal from the project root:

```sh
source .venv/bin/activate
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

Vite proxies `/api` to the local backend. For a different API location, see `frontend/.env.example`. The dashboard reads existing stored reviews and classifications; it does not start processing. Review Explorer filters and pagination are applied in the backend across all stored reviews. Sentiment and complaint pages show only completed results for the configured model, current version, and matching review fingerprint. Future AI workflows remain disabled. The hero and watch artwork are generated, unbranded illustrations, not official catalog images.

Run frontend checks from `frontend/` with `npm test` and `npm run build`.

## Phase 2 review intelligence

Set `GROQ_API_KEY` in your private `.env` and optionally change `GROQ_MODEL` (default `openai/gpt-oss-20b`). The backend and Phase 1 endpoints run without a key. Apply `alembic upgrade head`, then run a ten-review pilot with `python -m backend.app.classify`, or select up to 30 real Luna source IDs with `python -m backend.app.classify --source-ids 14 51 110`. Re-running skips completed results for unchanged review content. Failed records can be retried. Each review commits separately, so interruption is resumable. Groq JSON object mode is validated locally with Pydantic and exact source quotes; malformed or ungrounded outputs are retried at most three times and never silently accepted. The database stores attempt counts, error types, validation failures, and available usage for all attempts.

After approving the pilot, an explicit `python -m backend.app.classify --all --limit 25` processes up to 25 pending or failed Luna reviews; repeat for later batches. The CLI holds a local process lock, sends one request at a time, spaces all attempts by at least 15 seconds, and reserves a conservative 6,000-token rolling minute budget. A 429 follows Groq's `Retry-After` when present; daily exhaustion or a long cooldown stops the run. A persistent cooldown is checkpointed, so another run does not immediately retry. A local 160,000-token cap per UTC day adds a safety margin but cannot account for other projects using the same Groq account. No full batch is started automatically.

Classification rows are unique by review ID, model name, and classification version. The current version is defined by `CLASSIFICATION_VERSION` in `backend/app/services/classification.py`. Version 8 requests sentiment, complaint evidence, and praised features using Groq strict JSON Schema. Version 7 records remain stored separately; version 8 uses a consistent model and version. Severity and other fields omitted from version 8 remain unavailable. Quotes that do not exactly match the original title or review are marked as unavailable; their claims are excluded from evidence-backed complaint and feature counts. A changed review fingerprint is reclassified, while prior results remain in the database. Intelligence endpoints join reviews to results and select the configured model, current version, and matching fingerprint; distribution endpoints include completed results only. A future dashboard must use the same version and model for every metric and label pending or failed reviews separately rather than combining versions. The progress endpoint reports failures by type, attempt and validation counts, usage when returned, and any active cooldown. Raw failed model text is not stored; future parse failures store only safe missing-field or invalid-field paths. Earlier review 62 parse outputs were not retained, so their exact missing fields cannot be recovered.

Intelligence API: `/api/products/luna-smartwatch/intelligence/progress`, `/sentiment`, `/complaints`, `/praised-features`, and `/classifications?page=1&page_size=20`. Counts include only completed, current classifications. Progress reports analyzed, failed, and pending separately. Category and feature labels are AI interpretations of customer reports, not confirmed defects.

## Tests

```sh
python -m pytest -q
```

Tests use an in-memory SQLite database for isolated checks; the running application uses the configured PostgreSQL URL. PostgreSQL integration requires a local server and is not silently replaced by SQLite.

## Dataset inspection

The supplied CSV has 510 records and columns `id`, `product`, `review_text`, `title`, `rating`, `date`, and `source_url`. All records name Luna Smartwatch. There are 253 empty titles, no other missing fields, no duplicate IDs, no invalid ratings, and no malformed rows. All dates parse as `MM/DD/YYYY`; the range is 2023-12-17 through 2026-11-05. There are 213 repeated review texts, which remain separate source records. Review text lengths range from 1 to 290 characters. Ratings: 5★ 411, 4★ 78, 3★ 18, 2★ 1, 1★ 2. The raw file is ignored by Git pending redistribution rights.

### Local review retrieval (Phase 4)

Install the Python requirements and the PostgreSQL pgvector extension (on Homebrew PostgreSQL: `brew install pgvector`), then run `alembic upgrade head`. The database user must have permission to create the extension. Run `python -m backend.app.index_reviews` to embed complete Luna reviews locally. The first run downloads `sentence-transformers/all-MiniLM-L6-v2`; review text is processed locally and model files are cached in the ignored `.cache/huggingface` directory. Batches commit independently, and reruns skip unchanged reviews. Configure `EMBEDDING_MODEL` only with another 384-dimensional model; changing models creates a separate index and requires re-indexing.

Try `GET /api/retrieval/reviews?q=battery&rating=4&product_id=luna-smartwatch`. Similarity results are evidence candidates, not representative statistics or proof that a question can be answered. The default model is English-oriented; Urdu and Roman Urdu retrieval quality may vary. Ask ZeroInsight uses Groq only when a user submits a question with relevant retrieval results. It validates review IDs and exact evidence quotes before returning claims. Similarity and quote checks do not prove that a generated claim is entailed by its citation; users should review cited text. Urdu-script retrieval is currently disabled due to model limitations; Roman Urdu quality may vary. Chat history lasts for the current page session.

### Investigation backend (Phase 5)

Install the updated requirements and run `python -m backend.app.setup_checkpoints` once to create LangGraph's checkpoint tables in the configured PostgreSQL database. `POST /api/investigations` starts a Luna investigation; `GET /api/investigations/{id}` reads its persisted state, evidence and report; `POST /api/investigations/{id}/decision` accepts `approve`, `reject`, or `request_revision` and optional notes. Revision requests are recorded for human follow-up; no automatic rewrite is run. The workflow pauses for a human decision and resumes from PostgreSQL after a restart. A report may contain no findings when evidence is insufficient. Evidence uses similarity-selected reviews, not a representative sample; exact quote checks cannot establish that a finding is logically supported by its citation. The investigation interface displays persisted reports and evidence; decision controls are disabled pending authorization setup.

### Security for portfolio use

Set `FRONTEND_ORIGINS` to a comma-separated list of trusted frontend origins. AI and semantic retrieval endpoints have a basic per-client limit of 30 requests per minute per application process. This is not shared across workers and is not a substitute for a reverse proxy with shared rate limiting in a public deployment. The backend does not trust forwarded client IP headers.

Investigation decisions are disabled (HTTP 403) until an authentication and authorization design is approved. The frontend reflects this; existing reports, checkpoints and decisions remain available. For a local-only demo, a single-user access token is simple but needs secure delivery and rotation; for a public multi-user deployment, an identity provider with role-based access and session/CSRF controls provides individual accountability at greater setup cost. Neither option is implemented. The application has no user authentication, so do not expose its APIs or review data publicly until appropriate access controls are implemented.

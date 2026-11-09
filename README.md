# ZeroInsight AI

Independent portfolio project inspired by Zero Lifestyle. The backend analyzes the supplied **Luna Smartwatch** reviews only. The application includes review analytics, retrieval, and investigation workflows using Luna data only.

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

Vite proxies `/api` to the local backend. For a different API location, see `frontend/.env.example`. The dashboard reads existing stored reviews and classifications; it does not start processing. Review Explorer filters and pagination are applied in the backend across all stored reviews. Sentiment and complaint pages show only completed results for the configured model, current version, and matching review fingerprint. Ask ZeroInsight and Investigation Center use the existing retrieval and investigation workflows. The hero and watch artwork are generated, unbranded illustrations, not official catalog images.

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

Install the updated requirements and run `python -m backend.app.setup_checkpoints` once to create LangGraph's checkpoint tables in the configured PostgreSQL database. `POST /api/investigations` starts a Luna investigation; `GET /api/investigations/{id}` reads its persisted state, evidence and report; `POST /api/investigations/{id}/decision` accepts `approve`, `reject`, or `request_revision` and optional notes. Revision requests are recorded for human follow-up; no automatic rewrite is run. The workflow pauses for a human decision and resumes from PostgreSQL after a restart. A report may contain no findings when evidence is insufficient. Evidence uses similarity-selected reviews, not a representative sample; exact quote checks cannot establish that a finding is logically supported by its citation. The investigation interface displays persisted reports and evidence; decisions require administrator authorization.

### Security for portfolio use

Set `FRONTEND_ORIGINS` to a comma-separated list of trusted frontend origins. AI and semantic retrieval endpoints have a basic per-client limit of 30 requests per minute per application process. This is not shared across workers and is not a substitute for a reverse proxy with shared rate limiting in a public deployment. The backend does not trust forwarded client IP headers.

Investigation decisions require a single-user administrator bearer token. Generate a long random token locally with `python -c "import secrets; print(secrets.token_urlsafe(32))"`, put it in the backend `.env` as `ADMIN_TOKEN=<generated value>`, and restart the backend. Keep the value private and never commit or share the `.env` file. In Investigation Center, enter the token into the password field and select the verification arrow. The token is held in page memory only and is cleared when the page is refreshed or authorization is cleared. The server independently checks every decision; a missing or invalid token returns HTTP 401. If no token is configured, all decisions remain unavailable.

This shared token is for local development and private demonstrations only, not public authentication: it has no per-user identity, audit separation, session management, or secure transport by itself. Use HTTPS and an appropriate identity provider with role-based access before any public deployment. Read-only APIs have no user authentication; do not expose them or review data publicly without appropriate access controls.

## Docker Compose (local private use)

Requires Docker Engine and Compose v2. From the repository root:

```sh
cp .env.docker.example .env.docker
# Edit .env.docker privately: set POSTGRES_PASSWORD and the matching password in DOCKER_DATABASE_URL.
# Optionally set GROQ_API_KEY and a random ADMIN_TOKEN; do not put secrets in frontend settings.
docker compose --env-file .env.docker up --build -d
```

Open `http://127.0.0.1:8080`. The frontend serves the production build and proxies `/api` to FastAPI on the private Compose network. PostgreSQL and the backend have no host-published ports. The database health check gates initialization; the initialization service runs `alembic upgrade head` (including `CREATE EXTENSION vector`) and sets up the LangGraph checkpoint tables before the backend starts. The database uses a persistent named volume. The initialization does not import reviews, generate embeddings, run classifications, or call Groq. A new database is therefore empty, and data-dependent screens will remain empty until data is imported or restored. The embedding model may download on the first actual retrieval request; no embedding index is built automatically.

`POSTGRES_PASSWORD` and the URL password must match; use a URL-encoded password in `DOCKER_DATABASE_URL` if it contains special characters. The database image applies its password only when creating a fresh volume; changing the environment later does not change an existing database password. `DATABASE_URL` for local non-Docker development is separate. `GROQ_API_KEY`, `GROQ_MODEL`, `ADMIN_TOKEN`, `FRONTEND_ORIGINS`, and `EMBEDDING_MODEL` are backend runtime settings; the Groq key and admin token are optional until their respective features are used. The Compose frontend uses same-origin `/api` and needs no `VITE_API_BASE_URL` or other secret build variables. For the Vite development server, see `frontend/.env.example`. Do not put credentials in any `VITE_` variable or frontend bundle.

To stop the stack while preserving the database volume:

```sh
docker compose --env-file .env.docker down
```

To import an authorized local Luna CSV separately after startup:

```sh
backend_id=$(docker compose --env-file .env.docker ps -q backend)
docker cp /private/path/luna_510_reviews.csv "$backend_id:/tmp/luna_reviews.csv"
docker compose --env-file .env.docker exec backend python -m backend.app.ingest /tmp/luna_reviews.csv
docker compose --env-file .env.docker exec backend rm /tmp/luna_reviews.csv
```

Importing reviews does not restore existing classifications, embeddings, or investigations. Remove the temporary file even if ingestion fails, and do not commit or publish the CSV.

For a full private backup and restore (including reviews, embeddings, classifications and checkpoints), use a PostgreSQL custom-format dump. Store backups outside the repository, restrict access, and restore only into a fresh or disposable database; restore can overwrite existing data. Use a compatible PostgreSQL version: a newer-major dump may not restore to the Compose PostgreSQL 16 server.

```sh
docker compose --env-file .env.docker exec -T db pg_dump -U zeroinsight -Fc zeroinsight > /private/path/zeroinsight.backup
# With the target database running, after stopping any application that uses it:
docker compose --env-file .env.docker exec -T db pg_restore -U zeroinsight -d zeroinsight --clean --if-exists --no-owner < /private/path/zeroinsight.backup
```

For an existing database, back it up before running migrations. If startup fails, check `docker compose --env-file .env.docker ps` and `docker compose --env-file .env.docker logs initialize backend db` without sharing sensitive logs. Check that the configured passwords match, PostgreSQL is healthy, the database user can create the vector extension and checkpoint tables, and port 8080 is free. If the database starts with an old volume password, update credentials on the database or restore into a new volume; `docker compose down -v` **deletes the database volume**. If the app is empty, initialize or restore data separately as above. For model downloads, the backend needs access to Hugging Face and sufficient memory and disk.

This Compose configuration is for local private use. It does not provide HTTPS, public user authentication, or distributed rate limiting. The shared admin token is not suitable for public authentication. Do not expose it publicly without stronger identity controls, TLS, shared rate limiting, and a deployment-specific security review. Container tags and Python dependency ranges are not fully pinned; pin image digests and lock dependencies for reproducible production releases.

# FinSight AI — Financial Report Question-Answering Agent

Agentic RAG system for financial reports. **Done:** scaffold, database, PDF upload and extraction, chunking and embeddings, hybrid retrieval. financial calculator, grounded chat with citations. **Next:** agent tool routing, answer verification, dashboard charts.

## Run

```bash
cp .env.example .env     # set POSTGRES_PASSWORD, OPENAI_API_KEY, LLM_MODEL, EMBEDDING_MODEL
docker compose up --build
```

- Frontend: http://localhost:5173
- API docs: http://localhost:8000/docs
- Health: http://localhost:8000/api/health

## Local dev

```bash
docker compose up db -d      # point DATABASE_URL host at localhost
cd backend && pip install -r requirements.txt && uvicorn app.main:app --reload
cd frontend && npm install && npm run dev
```

## Tests

```bash
cd backend && pytest
```

## Phase 3: upload and extraction

1. Open http://localhost:5173/documents and drop `data/samples/Meridian_Industries_Annual_Report_FY2025_SAMPLE.pdf` (fictional demo data).
2. The status moves Uploaded, Processing, Extracting, Ready. The list polls automatically.
3. Click the row to see company, fiscal year, page count and the extracted tables, each linking to its page in the PDF.

Pipeline: validate (extension, `%PDF-` magic bytes, size, readable, not encrypted) then store under a random UUID, then process in the background: PyMuPDF text per page, pdfplumber tables, classification (income statement, balance sheet, cash flow, segment, expenses), and best-effort metadata. Scanned PDFs are rejected with a clear message (no OCR yet).

| Endpoint | Purpose |
|---|---|
| `POST /api/documents/upload` | Multipart upload, returns immediately (20 per minute per IP) |
| `GET /api/documents?page=&page_size=` | Paginated list |
| `GET /api/documents/{id}` | Detail with extracted tables |
| `GET /api/documents/{id}/file` | Original PDF (use `#page=N`) |
| `POST /api/documents/{id}/process` | Re-run processing |
| `DELETE /api/documents/{id}` | Delete record, extracted data and file |

Tests run against a real Postgres with pgvector (they skip if none is reachable): `docker compose up db -d`, then `cd backend && DATABASE_URL=postgresql+asyncpg://finsight:change-me@localhost:5432/finsight pytest`.

## Phase 4 and 5: chunking, embeddings, retrieval

Set these in `.env`, then run `docker compose up --build`:

```
OPENAI_API_KEY=your-key
EMBEDDING_MODEL=text-embedding-3-small
```

Existing documents must be re-processed once (the circular arrow on a document row).

- **Chunking** (`backend/app/rag/chunking.py`): a chunk never crosses a page, headings and tables are respected, each table is its own chunk (header repeated if split), running footers are removed, target about 800 tokens with overlap when a section is split.
- **Embeddings** (`rag/embeddings.py`): any OpenAI-compatible API, batched; identical text is never embedded twice, so re-processing costs nothing. The vector size must match `EMBEDDING_DIMENSIONS` (default 1536).
- **Retrieval** (`rag/retriever.py`): pgvector cosine search plus PostgreSQL full-text search, merged with Reciprocal Rank Fusion; filter by document or by text/table; accepts several query variants.
- **API:** `POST /api/search` (`query`, `document_ids`, `top_k`, `kind`) and `GET /api/documents/{id}/chunks`.
- **UI:** the "Search your documents" panel on the Documents page.

The tests use an offline stand-in embedder (`tests/stub_embedder.py`) so they run without a key; real embedding quality depends on your model.

## Phase 6 and 7: AI Analyst chat and financial calculator

Add a chat model to `.env` (together with the key and embedding model from Phase 4):

```
LLM_MODEL=your-chat-model-name
```

Open **AI Analyst**, pick a suggested question or type one. How an answer is produced (`backend/app/agents/financial_agent.py`):

1. A follow-up such as "What about 2024?" is rewritten into a standalone question using the last few messages.
2. The retriever returns the best passages (vector plus keyword search).
3. The LLM is told to answer only from the numbered sources, cite them, copy numbers exactly, never calculate, and ignore instructions found inside documents.
4. Citations are checked: ones pointing at sources that were not supplied are removed, and an answer with no valid citation is replaced by the fixed message "I could not find sufficient evidence in the uploaded financial reports to answer this question reliably."
5. Investment-advice questions get an informational note.

| Endpoint | Purpose |
|---|---|
| `POST /api/chat` | Ask a question (`message`, optional `conversation_id`, `document_ids`) |
| `GET /api/chat/history` | List conversations |
| `GET /api/chat/{id}` | Messages with sources |
| `DELETE /api/chat/{id}`, `DELETE /api/chat/history` | Delete one or all |
| `POST /api/calculate` | Exact calculation with formula and steps |
| `GET /api/calculate/metrics` | Supported metrics and their inputs |

Calculator metrics: percentage change, revenue growth, YoY growth, EPS growth, profit / gross / operating / net profit margin, CAGR, debt-to-equity, current ratio. Try it at http://localhost:8000/docs.

Known gaps until the agent phase: the chat does not call the calculator by itself yet (it reports the source values and says a calculation is needed), responses are not streamed, and there is no confidence level yet.

## Phase 8 — Agentic financial analysis

The AI Analyst now routes calculation questions to the deterministic financial calculator. The model is used only to identify the metric and extract candidate input values from retrieved report passages; every value must be found in the cited evidence before the calculator is called. Arithmetic is performed by `calculate_financial_metric`, not by the language model. The response includes the formula, calculation steps, and citations to the source passages. If a value is absent, unverifiable, malformed, or the metric is unsupported, the agent declines to calculate rather than inventing an input.

For table-heavy questions, the agent also searches persisted `financial_tables` records and adds a table to the prompt only when its document and page match a retrieved, citable passage. Comparison questions retrieve a larger evidence set and ask the grounded answerer to compare supported periods/items without performing arithmetic itself. `tool_used` in the chat response indicates `calculator`, `table_retrieval`, or `document_retrieval`.

The calculator currently supports percentage/revenue/YoY/EPS growth, profit/gross/operating/net margins, CAGR, debt-to-equity, and current ratio. The agent does not provide personalized investment advice.

# Vipassana AI Teacher

A conversational AI teacher grounded in Vipassana teaching documents. Uses a multi-agent RAG pipeline — a Generator answers from deep knowledge of the tradition, a Grounder enriches the response with citations from the indexed documents.

## Architecture

```
User question
      │
      ▼
[Retriever]  — embeds query, fetches top-5 passages from ChromaDB
      │
      ▼
[Generator]  — answers from Vipassana knowledge, cites relevant passages
      │
      ▼
[Grounder]   — adds citations, corrects any contradictions with documents
      │
      ▼
Answer + source citations
```

Both Generator and Grounder run via [OpenRouter](https://openrouter.ai), defaulting to `google/gemini-2.5-flash-preview`. Embeddings run locally using `all-MiniLM-L6-v2`.

## Requirements

- Python 3.10+
- `build-essential` + `python3-dev` (`apt install build-essential python3-dev` on Ubuntu — needed to compile `chroma-hnswlib`)
- `python3-venv` (`apt install python3-venv` on Ubuntu)
- An [OpenRouter](https://openrouter.ai) API key

## Setup

**1. Clone and enter the project**
```bash
git clone git@github.com:ash-hakande/vipassana-ai-teacher.git
cd vipassana-ai-teacher
```

**2. Create `.env`**
```bash
cp .env.example .env
```
Edit `.env` and fill in:
```
OPENROUTER_API_KEY=sk-or-v1-...
OPENROUTER_AGENT=google/gemini-2.5-flash-preview
OPENROUTER_REVIEWER_AGENT=google/gemini-2.5-flash-preview
PORT=8085
```

**3. Install dependencies**
```bash
./dev.sh install
```

**4. Add documents**

Drop Vipassana teaching PDFs or `.txt` files into the `documents/` folder, then ingest them:
```bash
./dev.sh ingest
```

Re-run ingest whenever you add new documents. Alternatively, copy an already-built `chroma_db/` from another machine:
```bash
scp -r chroma_db user@server:~/vipassana-ai-teacher/
```

**5. Start the server**
```bash
./dev.sh start
```

Open **http://localhost:8085** in your browser.

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/session/start` | Start a new conversation session |
| `POST` | `/session/{id}/respond` | Send a message, get a grounded response |
| `POST` | `/session/{id}/end` | End the session |
| `GET` | `/health` | Server status + document count |
| `GET` | `/debug/search?q=...` | Test raw retrieval without LLM calls |

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `OPENROUTER_API_KEY` | — | Required. Your OpenRouter API key |
| `OPENROUTER_AGENT` | `google/gemini-2.5-flash-preview` | Generator model |
| `OPENROUTER_REVIEWER_AGENT` | `google/gemini-2.5-flash-preview` | Grounder model |
| `PORT` | `8085` | Server port |
| `TOP_K_CHUNKS` | `5` | Number of document passages retrieved per query |
| `LOG_LEVEL` | `INFO` | Logging verbosity (`DEBUG`, `INFO`, `WARNING`) |
| `CHROMA_PERSIST_DIR` | `./chroma_db` | Vector store location |
| `DOCUMENTS_DIR` | `./documents` | Source documents location |

## Deploying to a Server

```bash
# On the server
git clone git@github.com:ash-hakande/vipassana-ai-teacher.git
cd vipassana-ai-teacher
cp .env.example .env && nano .env   # add your API key
./dev.sh install
./dev.sh start
```

To keep the server running after you disconnect, use a process manager like `systemd` or `screen`:
```bash
screen -S vipassana
./dev.sh start
# Ctrl+A then D to detach
```

# Vipassana AI Assistant

A conversational AI teacher grounded in Vipassana teaching documents. The project is now split into:

- `backend/`: FastAPI API, OpenRouter agents, ChromaDB retrieval, ingestion scripts.
- `frontend/`: Next.js chat UI that calls the backend API.

The backend keeps persistence simple: ChromaDB is stored on disk, and chat sessions remain in memory.

## API

| Method | Path | Description |
|---|---|---|
| `POST` | `/session/start` | Start a new conversation session |
| `POST` | `/session/{id}/respond` | Send a message and receive a grounded answer |
| `POST` | `/session/{id}/end` | End the session |
| `GET` | `/health` | Server status and indexed document count |
| `GET` | `/debug/search?q=...` | Raw retrieval results without LLM calls |

## Backend Setup

Create the backend environment file:

```bash
cp backend/.env.example backend/.env
```

Set at least:

```bash
OPENROUTER_API_KEY=sk-or-v1-...
CORS_EXTRA_ORIGINS=http://localhost:3000
```

Local Python workflow:

```bash
./backend/dev.sh install
./backend/dev.sh ingest
./backend/dev.sh start
```

The API runs at `http://localhost:9090`.

Local Docker workflow:

```bash
./dev.sh up
./dev.sh logs
```

## Frontend Setup

Create the frontend environment file:

```bash
cp frontend/.env.example frontend/.env.local
```

Set:

```bash
NEXT_PUBLIC_API_BASE_URL=http://localhost:9090
```

Run the app:

```bash
cd frontend
npm install
npm run dev
```

The frontend runs at `http://localhost:3000`.

## Documents and Ingestion

Place source PDFs or `.txt` files in `documents/`. Source metadata is read from `sources.json`.

Rebuild the Chroma index after changing documents:

```bash
./backend/dev.sh ingest
```

For Docker deployments, `documents/`, `sources.json`, and `chroma_db/` are mounted into the backend container.

## Production Backend Deployment

The backend deployment follows the same nginx + certbot pattern as `~/Projects/insula-be`.

1. Point your API domain DNS to the server.
2. Replace `api.example.com` in `nginx/nginx-initial.conf` and `nginx/nginx.conf`.
3. Set production values in `backend/.env`, including:

```bash
OPENROUTER_API_KEY=sk-or-v1-...
OPENROUTER_AGENT=google/gemini-2.5-flash-preview
OPENROUTER_REVIEWER_AGENT=google/gemini-2.5-flash-preview
LOG_LEVEL=INFO
CORS_EXTRA_ORIGINS=https://your-frontend-domain.com
```

4. Start with the initial HTTP nginx config to issue the certificate:

```bash
cp nginx/nginx-initial.conf nginx/nginx.conf
./dev.sh prod-up
docker compose run --rm certbot certonly --webroot --webroot-path=/var/www/certbot -d api.example.com
```

5. Restore the HTTPS `nginx/nginx.conf` content with your real domain, then restart:

```bash
./dev.sh prod-up
```

## Production Frontend Deployment

Deploy `frontend/` to a Next.js-compatible host such as Vercel, Netlify, or a Node host.

Set this environment variable in the frontend host:

```bash
NEXT_PUBLIC_API_BASE_URL=https://your-api-domain.com
```

Then build with:

```bash
npm run build
```

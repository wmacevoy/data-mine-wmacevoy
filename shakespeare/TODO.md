# TODOs Requiring Human Intervention

- [ ] Configure git-crypt in this repo and encrypt `private/**`:
  - Install git-crypt locally.
  - Initialize: `git-crypt init`.
  - Add users: `git-crypt add-gpg-user <YOUR_GPG_ID>` (or manage symmetric key).
  - Commit `.gitattributes` (already present) and re-encrypt if needed: `git-crypt lock`.
  - Verify: `git-crypt status` and ensure `private/secrets.env` is encrypted in Git.
- [ ] Provide real API keys in `private/secrets.env` (remains encrypted):
  - `OPENAI_API_KEY`, `EVENTBRITE_API_KEY`, `ARTS_GOV_API_KEY` (as applicable).
- [ ] Add Shakespeare corpus to `data/raw/` (text files):
  - Download from Project Gutenberg and place `.txt` files under `data/raw/`.
  - Run pipeline: POST `/build` or run notebooks to ingest + embed.
- [ ] (Optional) Configure a vector DB (e.g., Postgres + pgvector) instead of TF‑IDF.
- [ ] (Optional) Swap dummy generator with a real LLM call using your API key.
- [ ] (Optional) Schedule weekly ingestion (cron or GitHub Actions + server).

## Local Dev
- Build/run API:
  - `docker compose up --build`
  - Or locally: `uvicorn src.app:app --reload`
- Health check: `GET /health`
- Build index: `POST /build`
- Ask: `POST /ask` with body `{ "query": "Where can I see Macbeth in Colorado this summer?" }`

## Notes
- Sensitive files live in `private/` and are encrypted via git-crypt once configured.
- Data directories are tracked but large artifacts are `.gitignore`d by default.
# TODO (Human Interventions)

- [ ] git-crypt setup:
  - [ ] Install git-crypt (macOS: `brew install git-crypt`).
  - [ ] Initialize in this repo: `git-crypt init`.
  - [ ] Generate and export a new symmetric key (or re-use your policy):
    - `git-crypt export-key private/secret.key` (this path stays encrypted in git).
  - [ ] Add collaborators (GPG users) if needed: `git-crypt add-gpg-user <KEYID>`.
  - [ ] Commit and push after initialization so `private/**` is encrypted.

- [ ] Secrets management:
  - [ ] Populate `private/secrets.env` with API keys (e.g., `OPENAI_API_KEY`).
  - [ ] If `private/secret.key` was deleted earlier, either restore from backup or export a new key and share securely.

- [ ] Data ingestion:
  - [ ] Download Shakespeare texts (.txt) into `data/raw/` (e.g., Project Gutenberg).
  - [ ] Optionally add festival datasets/APIs credentials (Eventbrite, Arts.gov).

- [ ] Vector store (optional):
  - [ ] If using Postgres + pgvector, provision DB and set `POSTGRES_URL` in `private/secrets.env`.
  - [ ] Update code to persist embeddings there (current default is in-memory TF-IDF).

- [ ] App run and Docker:
  - [ ] Local: `uvicorn src.app:app --reload` (from repo root).
  - [ ] Docker: `docker compose up --build`.

- [ ] Evaluation tooling (optional):
  - [ ] Integrate TruLens/Langfuse/OpenAI Evals as desired.

Notes:
- The FastAPI service runs even without data, but `/ask` returns a helpful message until `.txt` files exist in `data/raw/`.
- All files under `private/` are marked for encryption in `.gitattributes`; ensure `git-crypt` is initialized to actually encrypt at rest in git.


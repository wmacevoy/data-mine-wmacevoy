# Shakespeare Festival Assistant (RAG LLM Project)

## Overview

This project demonstrates how to build a **Retrieval-Augmented Generation (RAG)** pipeline that empowers a Large Language Model (LLM) to answer questions about **Shakespeare and U.S. Shakespeare festivals**—without retraining or fine-tuning the model.

Instead of modifying the LLM’s parameters, we provide **contextual data retrieval** from a knowledge base that is dynamically updated. This architecture can be adapted to any subject domain.

---

## Objectives

* Combine **literary text data** (Shakespeare corpus) with **structured festival data** (event listings, metadata).
* Enable natural-language Q&A, recommendations, and summarizations.
* Demonstrate **best practices** for RAG pipelines: ingestion, embedding, retrieval, prompting, and evaluation.

---

## Project Structure

```
rag-llm-agent/
├── README.md                  # This file
├── data/
│   ├── raw/                   # Shakespeare corpus, event listings, etc.
│   ├── processed/             # Cleaned and chunked text data
│   └── embeddings/            # Vectorized data storage
├── notebooks/
│   ├── 00_initialize.ipynb    # Download raw Shakespeare texts (Project Gutenberg)
│   ├── 01_ingestion.ipynb     # Load and clean datasets
│   ├── 02_embedding.ipynb     # Generate embeddings for text
│   ├── 03_retrieval.ipynb     # Retrieve relevant context from DB
│   ├── 04_generation.ipynb    # LLM query + prompt assembly
│   └── 05_evaluation.ipynb    # Evaluate retrieval & response quality
├── src/
│   ├── ingest.py              # ETL pipeline (scraping, cleaning)
│   ├── embed.py               # Generate embeddings
│   ├── retrieve.py            # Query vector database
│   ├── generate.py            # Prompt LLM with context
│   └── app.py                 # FastAPI/Streamlit app interface
├── config/
│   ├── settings.yaml          # Model, DB, and embedding configs
│   └── secrets.env            # API keys (excluded from git)
├── requirements.txt           # Dependencies
└── docker-compose.yml         # Optional deployment setup
```

---

## Data Sources

### Shakespeare Corpus

* Source: [Project Gutenberg](https://www.gutenberg.org/)
* Files: all plays and sonnets (plain text)
* Preprocessing: tokenization, sentence segmentation, stopword removal

### Festival Data

* Source APIs: Eventbrite, Arts.gov, Shakespeare Theater Association
* Fields: festival name, location, date, play, summary, link
* Update frequency: weekly cron job

---

## Architecture

### Core Components

| Component        | Purpose                                | Tools                                              |
| ---------------- | -------------------------------------- | -------------------------------------------------- |
| **Ingestion**    | Collect, clean, and normalize datasets | Python, Pandas, BeautifulSoup                      |
| **Embedding**    | Convert text into numerical vectors    | OpenAI `text-embedding-3-large`, Cohere, or Voyage |
| **Vector Store** | Store embeddings and metadata          | Postgres + `pgvector` (persistent volume)          |
| **Retrieval**    | Find relevant chunks per user query    | Hybrid search: sparse TF‑IDF + dense LSA (SVD)     |
| **Generation**   | Prompt LLM with retrieved context      | GPT‑5‑turbo, Claude 3.5, or Mistral                |

### Example Flow

1. User: *“Where can I see Macbeth in Colorado this summer?”*
2. Query → embedding → top‑K context retrieval
3. Prompt assembled with retrieved snippets
4. LLM generates grounded answer

---

## Hybrid Retrieval

This project uses a hybrid retriever combining:

- Sparse TF‑IDF cosine similarity
- Dense LSA embeddings via TruncatedSVD on the TF‑IDF space (row‑normalized)

Final score for a document i is:

\[ score_i = w_\text{sparse} \cdot \text{cos}(tfidf_i, tfidf_q) + w_\text{dense} \cdot \text{cos}(svd_i, svd_q) \]

Weights and dimensions are configurable in `config/settings.yaml`:

```
retrieval:
  method: "hybrid"
  weights:
    sparse: 0.5
    dense: 0.5
  dense_dim: 256
```

### Model Selection (Generation + Embeddings)

Control models via `config/settings.yaml`:

```
generation:
  # "mock" uses a local template (offline). To use OpenAI, prefix with "openai-".
  # Example: "openai-gpt-4o-mini"
  model: "mock"

embeddings:
  # Choose between classic IR (tfidf) and OpenAI embeddings
  method: tfidf   # or "openai"
  # Only used when method=openai
  model: text-embedding-3-small
```

- When `embeddings.method: tfidf`, the pipeline fits TF–IDF + TruncatedSVD locally and saves
  `vectorizer.joblib`, `tfidf.npz`, `svd.joblib`, and `dense.npy`.
- When `embeddings.method: openai`, it calls the OpenAI Embeddings API and saves only `dense.npy`.
- For Postgres indexing with pgvector, table vector dimension is chosen automatically based on config.

Run the build to (re)compute artifacts:

- API: `POST /build` (full build) or `POST /rebuild` (incremental, new/modified files)
- Notebooks: `00_initialize.ipynb` (optional) → `01_ingestion.ipynb` → `02_embedding.ipynb`

## Prompt Template

```
System: You are a Shakespearean culture assistant.
User: {{user_query}}
Context:
{{retrieved_context}}
Task: Answer the user using the context. Include dates and locations. Avoid speculation.
```

---

## Evaluation Metrics

| Metric             | Description                                  |
| ------------------ | -------------------------------------------- |
| **Context Recall** | % of relevant facts retrieved                |
| **Faithfulness**   | Accuracy relative to context                 |
| **Relevance**      | Semantic similarity between query and answer |
| **Latency**        | Response time end‑to‑end                     |

Recommended tools: **TruLens**, **Langfuse**, **OpenAI Evals**.

---

## Deployment

* Serve via **FastAPI** or **Streamlit** web interface.
* Containerize with **Docker Compose**.
* Schedule nightly ingestion of new festival data.

### Local Dashboard

- Static dashboard is served at `http://localhost:8080` (index.html and admin.html)
- Start everything and open browser + Jupyter: `./run.sh all`
- API base is `http://localhost:8000` and supports CORS from `http://localhost:8080`

### Secrets

All secrets are read from the encrypted `private/` directory using `private/secrets.env`.

Precedence: environment variables > `private/secrets.env`.
The app loads these on startup and exposes presence (not values) at `GET /config`.

### Example `docker-compose.yml`

```yaml
services:
  app:
    build: .
    ports:
      - "8000:8000"
    env_file: private/secrets.env
  db:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_DB: rag
      POSTGRES_USER: raguser
      POSTGRES_PASSWORD: ragpass
    volumes:
      - ./data/db:/var/lib/postgresql/data
    ports:
      - "5432:5432"

### Idempotent Indexing

Raw files under `data/raw/` are chunked with origin metadata tracked in Postgres:

- `documents(origin_path, origin_mtime, origin_sha256)`
- `chunks(document_id, chunk_index, chunk_sha256, content, embedding vector)`

The app performs upserts so re-processing the same file updates existing rows.
Use `POST /rebuild` to process only new/modified files based on file timestamps and content hashes.
```

---

## Extensions

* Add **user memory** for personalization.
* Use **hybrid retrieval** (vector + keyword) for improved recall.
* Integrate with **LangChain**, **LlamaIndex**, or **DSPy** for orchestration.
* Replace static data with **live APIs** for real‑time festival updates.

---

## License

MIT License © 2025 — Created for educational and demonstration purposes.

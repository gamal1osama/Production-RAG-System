# MiniRAG

MiniRAG is a compact, production-minded Retrieval-Augmented Generation (RAG) service built with FastAPI. It supports document upload, chunking, vector indexing, semantic search, and answer generation using configurable LLM and vector backends.

This README is intentionally long and explicit. It documents how each part of the codebase works, the project flow, technologies used, design patterns, and how the architecture supports a database migration with minimal refactoring.

---

## At a Glance

- **Core goal:** upload files -> split into chunks -> index into vector DB -> search -> generate answers.
- **API-first:** FastAPI endpoints under `/api/v1`.
- **Pluggable backends:** LLM and vector DB are selected via factories and interfaces.
- **Relational persistence:** PostgreSQL with SQLAlchemy + Alembic migrations.
- **Local vector storage:** Qdrant local DB path (default).

---

## Project Structure (by responsibility)

```
src/
  main.py                  # app bootstrap, dependency setup
  routes/                  # HTTP layer (API)
  controllers/             # orchestration + business logic
  models/                  # data-access layer + DB schemas
  stores/                  # external services (LLM + VectorDB)
  helpers/                 # app configuration
  assets/                  # file uploads + local vector DB storage
```

### Routing Layer (HTTP)
- **[src/routes/base.py](src/routes/base.py)**: health/info endpoint.
- **[src/routes/data.py](src/routes/data.py)**: upload files, process chunks.
- **[src/routes/nlp.py](src/routes/nlp.py)**: index, search, answer.

### Controllers (Orchestration)
- **[src/controllers/DataController.py](src/controllers/DataController.py)**: file validation + file path logic.
- **[src/controllers/ProcessController.py](src/controllers/ProcessController.py)**: load file + chunking logic.
- **[src/controllers/NLPController.py](src/controllers/NLPController.py)**: indexing, search, RAG answer.
- **[src/controllers/ProjectController.py](src/controllers/ProjectController.py)**: project-specific storage paths.

### Models (Persistence)
- **[src/models/ProjectModel.py](src/models/ProjectModel.py)**: CRUD for projects.
- **[src/models/AssetModel.py](src/models/AssetModel.py)**: file asset records.
- **[src/models/ChunkModel.py](src/models/ChunkModel.py)**: chunk records + pagination.
- **[src/models/db_schemas/minirag/schemas](src/models/db_schemas/minirag/schemas)**: SQLAlchemy tables.

### Stores (External Services)
- **LLM providers:** OpenAI, Cohere via **[LLMProviderFactory](src/stores/llm/LLMProviderFactory.py)**.
- **Vector DB providers:** Qdrant via **[VectorDBProviderFactory](src/stores/vectordb/VectorDBProviderFactory.py)**.
- **Template rendering:** prompt templates via **[TemplateParser](src/stores/llm/templates/template_parser.py)**.

---

## End-to-End Flow (RAG lifecycle)

### 1) Upload a file
1. HTTP request to `/api/v1/data/upload/{project_id}`.
2. `DataController.validate_uploaded_file()` verifies type and size.
3. File is persisted in `assets/files/{project_id}/`.
4. Asset metadata is stored in PostgreSQL (`assets` table).

### 2) Process files into chunks
1. HTTP request to `/api/v1/data/process/{project_id}`.
2. `ProcessController` loads files (TXT/PDF).
3. `RecursiveCharacterTextSplitter` chunks data.
4. Chunk metadata is stored in PostgreSQL (`chunks` table).

### 3) Index chunks into the vector DB
1. HTTP request to `/api/v1/nlp/index/push/{project_id}`.
2. `NLPController.index_into_db()` embeds chunks using selected embedding provider.
3. Chunks are written into the configured vector DB collection.

### 4) Search and answer
1. HTTP request to `/api/v1/nlp/index/search/{project_id}` performs semantic search.
2. HTTP request to `/api/v1/nlp/index/answer/{project_id}` builds a RAG prompt.
3. Generation provider returns a final answer.

---

## Technologies Used

- **FastAPI**: API layer, async support, dependency injection.
- **SQLAlchemy (async)**: relational persistence layer.
- **Alembic**: schema migration and versioning.
- **Qdrant**: vector store (local path client).
- **OpenAI / Cohere**: LLM + embeddings providers.
- **LangChain**: document loading and text splitting.
- **PyMuPDF**: PDF ingestion.
- **Docker Compose**: local services (Postgres with pgvector, MongoDB legacy).

---

## Design Patterns Used (critical)

The project intentionally uses multiple patterns to make swapping services and refactoring safe:

1) **Factory Pattern**
	- `LLMProviderFactory` and `VectorDBProviderFactory` create concrete providers from config.
	- The rest of the system depends only on the interface, not the concrete type.

2) **Strategy Pattern**
	- `LLMInterface` and `VectorDBInterface` define pluggable behaviors.
	- OpenAI/Cohere and Qdrant implementations provide interchangeable strategies.

3) **Repository / Data Access Layer**
	- `ProjectModel`, `AssetModel`, and `ChunkModel` encapsulate DB operations.
	- Routes/controllers never embed SQL details, which makes DB shifts localized.

4) **Dependency Injection via App State**
	- `main.py` wires `db_client`, `vector_db_client`, `generation_client`, `embedding_client`.
	- Controllers accept these dependencies rather than instantiating them directly.

5) **Layered Architecture (HTTP -> Controller -> Model -> Store)**
	- Clear separation of concerns reduces coupling.
	- Each layer has a narrow responsibility, enabling isolated refactors.

---

## SOLID Principles: How the Code Enforces Them

- **Single Responsibility**: Controllers orchestrate flow; models only handle persistence; providers only handle external services.
- **Open/Closed**: Adding a new LLM or vector DB is done by implementing an interface and registering in the factory.
- **Liskov Substitution**: All providers implement shared interfaces and can replace each other without breaking behavior.
- **Interface Segregation**: Separate interfaces for LLM and Vector DB keep contracts minimal and focused.
- **Dependency Inversion**: High-level controllers depend on abstractions (`LLMInterface`, `VectorDBInterface`), not concrete classes.

---

## Database Design (PostgreSQL)

**Tables (SQLAlchemy + Alembic):**

- `projects`
  - Primary entity for each logical data workspace.
- `assets`
  - Uploaded files and metadata.
- `chunks`
  - Split chunks linked to assets and projects.

**Relationships:**
- `Project` 1..N `Asset`
- `Project` 1..N `DataChunk`
- `Asset` 1..N `DataChunk`

**Highlights:**
- Uses `JSONB` for flexible metadata (`asset_config`, `chunk_metadata`).
- Indexed foreign keys for faster project/asset filtering.
- Async SQLAlchemy sessions for concurrency-safe operations.

---

## Vector Database (Qdrant and pgvector)

**Qdrant (local path mode)**
- Collection per project: `collection_{project_id}`.
- Embedding size defined by config (e.g., 1024).
- Records store: `text` + `metadata` + `score` returned by Qdrant.
- Local persistence path: `assets/database/{VECTOR_DB_PATH}`.

**pgvector (PostgreSQL extension)**
- Uses the Postgres service and keeps vector data alongside relational data.
- Ideal when you want a single database stack and simpler infra.

**Simplest switch (env-driven):**
- Set `VECTOR_DB_BACKEND` in your environment file to choose the backend.
- No code changes required; the factories resolve the provider at startup.

---

## Database Migration: MongoDB -> PostgreSQL (minimal refactor)

The codebase is structured to make a database swap mostly a **model-layer change**:

1) **DB access is isolated in models**
	- Controllers call `ProjectModel`, `AssetModel`, `ChunkModel` only.
	- SQL details never leak into routing or processing logic.

2) **Schema is managed externally via Alembic**
	- Tables and relationships are defined once in SQLAlchemy schemas.
	- Changes are tracked and migrated without rewriting business logic.

3) **Service boundaries are clean**
	- File handling, chunking, LLM calls, and vector search do not depend on the relational DB choice.

**Note:** This repo still contains MongoDB references in Docker and dependencies. They are legacy artifacts and can be removed once you are fully confident in the Postgres path.

The power of a strong software base (clean layering, interfaces, and factories) is what made the MongoDB -> PostgreSQL shift straightforward, and it now enables vector backend switching through the environment file without large refactors.

---

## Docker Compose (local services)

Docker provides two services:

- **PostgreSQL (pgvector image)**: main relational database (`5432`).
- **MongoDB**: legacy/experimental service (`27017`).

Use it for local development:

```bash
cp docker/.env.example docker/.env
# edit docker/.env to set credentials
docker compose -f docker/docker-compose.yml up -d
```

If you only use Postgres, MongoDB can be disabled.

---

## Alembic (Schema Migrations)

Alembic lives under:

```
src/models/db_schemas/minirag/
```

Quick start:

```bash
cd src/models/db_schemas/minirag
cp alembic.ini.example alembic.ini

# edit alembic.ini to set sqlalchemy.url
alembic revision --autogenerate -m "describe change"
alembic upgrade head
```

Key points:
- `alembic.ini` is local and git-ignored.
- `alembic/env.py` loads `SQLAlchemyBase.metadata` for autogenerate.

For the detailed Alembic workflow and troubleshooting notes, see
[src/models/db_schemas/minirag/README.md](src/models/db_schemas/minirag/README.md).

---

## Configuration (.env)

All configuration is loaded via `pydantic-settings` in **[src/helpers/config.py](src/helpers/config.py)**.

Example keys:

```
APP_NAME, APP_VERSION
POSTGRES_HOST, POSTGRES_PORT, POSTGRES_MAIN_DB, POSTGRES_USER, POSTGRES_PASSWORD
GENERATION_BACKEND, EMBEDDING_BACKEND
OPENAI_API_KEY, COHERE_API_KEY
VECTOR_DB_BACKEND, VECTOR_DB_PATH, VECTOR_DB_DISTANCE_METHOD
```

---

## API Endpoints

**Data**
- `POST /api/v1/data/upload/{project_id}`
- `POST /api/v1/data/process/{project_id}`

**NLP / Index**
- `POST /api/v1/nlp/index/push/{project_id}`
- `GET  /api/v1/nlp/index/info/{project_id}`
- `POST /api/v1/nlp/index/search/{project_id}`
- `POST /api/v1/nlp/index/answer/{project_id}`

---

## Setup and Run

### Requirements
- Python 3.8+

### Install
```bash
sudo apt update
sudo apt install libpq-dev gcc python3-dev
pip install -r src/requirements.txt
```

### Run API
```bash
cd src
uvicorn main:app --reload --host 0.0.0.0 --port 5000
```

---

## Why This Project is Solid

- **Layered architecture** minimizes coupling and keeps responsibilities clean.
- **Strict contracts** via interfaces reduce risk when swapping providers.
- **Async DB and I/O** for scalability and non-blocking performance.
- **Schema migration discipline** with Alembic keeps data evolution safe.
- **Config-driven behavior** makes environment and vendor changes predictable.



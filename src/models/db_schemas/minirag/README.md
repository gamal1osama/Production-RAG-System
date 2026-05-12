# Alembic Usage (MiniRAG)

This folder contains the Alembic config and migration scripts for the MiniRAG database schema.

This guide focuses on the exact workflow used in this repository and common recovery steps when
Alembic autogenerate does not behave as expected.

## Quick start

1) Create the local config file:

```bash
cp alembic.ini.example alembic.ini
```

2) Edit `alembic.ini` and set `sqlalchemy.url` to your database URL.

3) Run Alembic from this folder:

```bash
# Create a new migration (autogenerate from models)
alembic revision --autogenerate -m "describe change"

# Apply migrations
alembic upgrade head
```

## Detailed workflow (recommended)

### 1) Verify the database URL

`alembic.ini` is local and git-ignored, so every developer must set it:

```
sqlalchemy.url = postgresql://USER:PASSWORD@HOST:5432/DBNAME
```

### 2) Ensure Alembic can see the models

The autogenerate step depends on `SQLAlchemyBase.metadata` being populated with all tables.
In this repo, that is wired in:

```
src/models/db_schemas/minirag/alembic/env.py
```

If you add a new model, make sure it is imported in the schema package so the metadata
contains the new table.

### 3) Create a migration

```
alembic revision --autogenerate -m "add your change summary"
```

Review the generated file under:

```
src/models/db_schemas/minirag/alembic/versions/
```

### 4) Apply the migration

```
alembic upgrade head
```

### 5) Verify the schema

```
alembic current
alembic history
```

## Common commands

```bash
# Show current revision
alembic current

# List migration history
alembic history

# Downgrade one step
alembic downgrade -1
```

## Notes

- Keep `alembic.ini` local; it is ignored by git.
- If Alembic cannot find your models, check `alembic/env.py` for the import paths.

## Troubleshooting

### Autogenerate produced an empty migration

Possible causes:
- The model module is not imported, so it never registers with `SQLAlchemyBase.metadata`.
- You are running Alembic from the wrong folder, so import paths resolve incorrectly.

Fix:
- Ensure the model file is imported in the schema package, then rerun autogenerate.
- Run Alembic from `src/models/db_schemas/minirag`.

### "Target database is not up to date"

This usually means you changed models without applying the last migration.

Fix:
- Run `alembic upgrade head` before creating a new migration.

### "Can't locate revision" or broken history

Fix:
- Verify the migration file exists under `alembic/versions`.
- Check for accidental deletion or renaming.

### DB connection errors

Fix:
- Confirm `sqlalchemy.url` in `alembic.ini` is correct.
- Ensure the database service is running (Docker or local install).

### Postgres schema not updated after migration

Fix:
- Confirm you are connecting to the same database used by the application.
- Run `alembic current` to verify the active revision.

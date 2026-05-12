# Alembic Usage (MiniRAG)

This folder contains the Alembic config and migration scripts for the MiniRAG database schema.

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

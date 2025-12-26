# Database Migrations

## Overview

This directory contains SQL migrations for the billing_service database.

## Running Migrations

### Apply Migration (UP)
```bash
# Connect to PostgreSQL and run:
psql -U postgres -d billing_service -f migrations/001_create_credit_tables.sql
```

### Rollback Migration (DOWN)
```bash
# Connect to PostgreSQL and run:
psql -U postgres -d billing_service -f migrations/001_create_credit_tables_down.sql
```

### Using Python/SQLModel (Alternative)
```python
# In Python code (for development):
from sqlmodel import create_engine, SQLModel
from src.domain.credit_ledger import CreditLedger
from src.domain.credit_transaction import CreditTransaction

engine = create_engine("postgresql://postgres:postgres@localhost:5432/billing_service")
SQLModel.metadata.create_all(engine)
```

## Migration List

| # | Name | Description | Date |
|---|------|-------------|------|
| 001 | create_billing_tables | Create billing service schema (credit_ledgers, credit_transactions, subscriptions, invoices, invoice_lines) | 2024-12-26 |

## Future: Alembic Integration

For production, consider adding Alembic for version-controlled migrations:

```bash
# Add to pyproject.toml:
# "alembic>=1.13.0"

# Initialize Alembic:
# uv add alembic
# uv run alembic init alembic

# Generate auto-migration:
# uv run alembic revision --autogenerate -m "create credit tables"

# Apply migration:
# uv run alembic upgrade head
```

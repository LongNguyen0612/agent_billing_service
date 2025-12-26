-- Migration: 001_create_billing_tables
-- Description: Create billing service schema (credit_ledgers, credit_transactions, subscriptions, invoices, invoice_lines)
-- Date: 2024-12-26
-- Story: 1.1 - Implement Credit Domain Entities (Updated Schema)

-- =====================================================
-- UP MIGRATION
-- =====================================================

-- Create credit_ledgers table
CREATE TABLE IF NOT EXISTS credit_ledgers (
    id BIGSERIAL PRIMARY KEY,
    tenant_id VARCHAR(255) NOT NULL,
    balance NUMERIC(18, 6) NOT NULL DEFAULT 0,
    monthly_limit NUMERIC(18, 6),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Constraints
    CONSTRAINT balance_non_negative CHECK (balance >= 0),
    CONSTRAINT monthly_limit_non_negative CHECK (monthly_limit IS NULL OR monthly_limit >= 0),
    CONSTRAINT uq_credit_ledgers_tenant_id UNIQUE (tenant_id)
);

-- Create index on tenant_id (unique index)
CREATE UNIQUE INDEX IF NOT EXISTS ix_credit_ledgers_tenant_id ON credit_ledgers(tenant_id);

-- Create credit_transactions table
CREATE TABLE IF NOT EXISTS credit_transactions (
    id BIGSERIAL PRIMARY KEY,
    tenant_id VARCHAR(255) NOT NULL,
    ledger_id BIGINT NOT NULL,
    transaction_type VARCHAR(20) NOT NULL,
    amount NUMERIC(18, 6) NOT NULL,
    reference_type VARCHAR(50),
    reference_id VARCHAR(255),
    idempotency_key VARCHAR(255) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Foreign Key
    CONSTRAINT fk_credit_transactions_ledger_id
        FOREIGN KEY (ledger_id)
        REFERENCES credit_ledgers(id)
        ON DELETE CASCADE,

    -- Unique constraint on idempotency_key
    CONSTRAINT uq_credit_transactions_idempotency_key UNIQUE (idempotency_key)
);

-- Create indexes on credit_transactions
CREATE UNIQUE INDEX IF NOT EXISTS ix_credit_transactions_idempotency_key
    ON credit_transactions(idempotency_key);

CREATE INDEX IF NOT EXISTS ix_credit_transactions_tenant_id
    ON credit_transactions(tenant_id);

CREATE INDEX IF NOT EXISTS ix_credit_transactions_created_at
    ON credit_transactions(created_at);

CREATE INDEX IF NOT EXISTS ix_credit_transactions_reference
    ON credit_transactions(reference_type, reference_id);

-- Create subscriptions table
CREATE TABLE IF NOT EXISTS subscriptions (
    id BIGSERIAL PRIMARY KEY,
    tenant_id VARCHAR(255) NOT NULL,
    status VARCHAR(20) NOT NULL,
    plan_name VARCHAR(100) NOT NULL,
    monthly_credits NUMERIC(18, 6) NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes on subscriptions
CREATE INDEX IF NOT EXISTS ix_subscriptions_tenant_id
    ON subscriptions(tenant_id);

CREATE INDEX IF NOT EXISTS ix_subscriptions_status
    ON subscriptions(status);

-- Create invoices table
CREATE TABLE IF NOT EXISTS invoices (
    id BIGSERIAL PRIMARY KEY,
    tenant_id VARCHAR(255) NOT NULL,
    invoice_number VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL,
    total_amount NUMERIC(18, 6) NOT NULL,
    currency VARCHAR(3) NOT NULL DEFAULT 'USD',
    billing_period_start DATE NOT NULL,
    billing_period_end DATE NOT NULL,
    issued_at TIMESTAMP,
    paid_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Unique constraint on invoice_number
    CONSTRAINT uq_invoices_invoice_number UNIQUE (invoice_number)
);

-- Create indexes on invoices
CREATE INDEX IF NOT EXISTS ix_invoices_tenant_id
    ON invoices(tenant_id);

CREATE INDEX IF NOT EXISTS ix_invoices_status
    ON invoices(status);

CREATE UNIQUE INDEX IF NOT EXISTS ix_invoices_invoice_number
    ON invoices(invoice_number);

-- Create invoice_lines table
CREATE TABLE IF NOT EXISTS invoice_lines (
    id BIGSERIAL PRIMARY KEY,
    invoice_id BIGINT NOT NULL,
    description VARCHAR(255) NOT NULL,
    quantity NUMERIC(18, 6) NOT NULL,
    unit_price NUMERIC(18, 6) NOT NULL,
    total_price NUMERIC(18, 6) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Foreign Key
    CONSTRAINT fk_invoice_lines_invoice_id
        FOREIGN KEY (invoice_id)
        REFERENCES invoices(id)
        ON DELETE CASCADE
);

-- Create index on invoice_lines
CREATE INDEX IF NOT EXISTS ix_invoice_lines_invoice_id
    ON invoice_lines(invoice_id);

-- =====================================================
-- VERIFICATION QUERIES (Optional - run after migration)
-- =====================================================

-- Verify tables created
-- SELECT table_name FROM information_schema.tables
-- WHERE table_name IN ('credit_ledgers', 'credit_transactions', 'subscriptions', 'invoices', 'invoice_lines');

-- Verify constraints
-- SELECT constraint_name, constraint_type
-- FROM information_schema.table_constraints
-- WHERE table_name IN ('credit_ledgers', 'credit_transactions', 'subscriptions', 'invoices', 'invoice_lines');

-- Verify indexes
-- SELECT indexname, tablename
-- FROM pg_indexes
-- WHERE tablename IN ('credit_ledgers', 'credit_transactions', 'subscriptions', 'invoices', 'invoice_lines');

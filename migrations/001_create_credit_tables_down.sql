-- Migration: 001_create_billing_tables (ROLLBACK)
-- Description: Drop all billing service tables
-- Date: 2024-12-26
-- Story: 1.1 - Implement Credit Domain Entities (Updated Schema)

-- =====================================================
-- DOWN MIGRATION (ROLLBACK)
-- =====================================================

-- Drop tables in reverse order (respecting foreign keys)
DROP TABLE IF EXISTS invoice_lines CASCADE;
DROP TABLE IF EXISTS invoices CASCADE;
DROP TABLE IF EXISTS subscriptions CASCADE;
DROP TABLE IF EXISTS credit_transactions CASCADE;
DROP TABLE IF EXISTS credit_ledgers CASCADE;

-- Note: Indexes and constraints are automatically dropped with CASCADE

"""Credit Transaction Domain Entity

Immutable append-only audit trail of all credit mutations.
Each transaction records balance changes with complete context.
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional
from sqlmodel import Field, Column, Index
from sqlalchemy import ForeignKey, BigInteger, Numeric, String
from src.domain.base import BaseModel


class TransactionType(str, Enum):
    """Credit transaction types"""
    CONSUME = "consume"      # Credits consumed (pipeline execution)
    REFUND = "refund"        # Credits refunded (compensation)
    ALLOCATE = "allocate"    # Credits allocated/purchased by user
    ADJUST = "adjust"        # Manual admin adjustment


class CreditTransaction(BaseModel, table=True):
    """
    Credit Transaction - Immutable audit trail of credit mutations

    Domain Rules:
    - Transactions are immutable (append-only)
    - idempotency_key must be unique (prevents double-billing)
    - Linked to CreditLedger via ledger_id
    - reference_type/reference_id provide context (e.g., "pipeline_run", "invoice")

    Transaction Types:
    - CONSUME: Credits consumed during usage (pipeline execution)
    - REFUND: Credits refunded back (failure compensation)
    - ALLOCATE: Credits added via purchase or allocation
    - ADJUST: Manual admin adjustment (can be positive or negative)
    """

    __tablename__ = "credit_transactions"
    __table_args__ = (
        Index('ix_credit_transactions_created_at', 'created_at'),
        Index('ix_credit_transactions_reference', 'reference_type', 'reference_id'),
    )

    id: int = Field(
        sa_column=Column(BigInteger, primary_key=True, autoincrement=True),
        description="Unique transaction identifier (auto-increment)"
    )

    tenant_id: str = Field(
        index=True,
        description="Tenant ID for query optimization"
    )

    ledger_id: int = Field(
        sa_column=Column(BigInteger, ForeignKey("credit_ledgers.id", ondelete="CASCADE"), nullable=False),
        description="Foreign key to CreditLedger"
    )

    transaction_type: TransactionType = Field(
        description="Type of transaction (consume, refund, allocate, adjust)"
    )

    amount: Decimal = Field(
        sa_column=Column(Numeric(18, 6), nullable=False),
        description="Credit amount (precision: 18,6)"
    )

    balance_before: Decimal = Field(
        sa_column=Column(Numeric(18, 6), nullable=False),
        description="Balance before transaction (for idempotency)"
    )

    balance_after: Decimal = Field(
        sa_column=Column(Numeric(18, 6), nullable=False),
        description="Balance after transaction (for idempotency)"
    )

    reference_type: Optional[str] = Field(
        default=None,
        sa_column=Column(String(50), nullable=True),
        description="Type of reference (e.g., 'pipeline_run', 'invoice', 'adjustment')"
    )

    reference_id: Optional[str] = Field(
        default=None,
        sa_column=Column(String(255), nullable=True),
        description="ID of referenced entity (e.g., pipeline_run_id, invoice_id)"
    )

    idempotency_key: str = Field(
        unique=True,
        index=True,
        description="Unique key for idempotent operations (e.g., pipeline_id:step_id)"
    )

    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Transaction timestamp (immutable)"
    )

    class Config:
        """SQLModel configuration"""
        json_schema_extra = {
            "example": {
                "id": 1,
                "tenant_id": "tenant_xyz789",
                "ledger_id": 1,
                "transaction_type": "consume",
                "amount": "30.500000",
                "balance_before": "1000.000000",
                "balance_after": "969.500000",
                "reference_type": "pipeline_run",
                "reference_id": "run_456",
                "idempotency_key": "pipeline_456:step_789",
                "created_at": "2024-01-01T00:00:00Z"
            }
        }

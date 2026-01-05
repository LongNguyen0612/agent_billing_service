"""Credit Ledger Domain Entity

Tracks credit balance per tenant. Each tenant has exactly one ledger.
Balance is always >= 0 and updated through CreditTransactions.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional
from sqlmodel import Field, Column, Index
from sqlalchemy import CheckConstraint, BigInteger, Numeric
from src.domain.base import BaseModel


class CreditLedger(BaseModel, table=True):
    """
    Credit Ledger - Tracks tenant credit balance

    Domain Rules:
    - One ledger per tenant (tenant_id is unique)
    - Balance must be non-negative
    - Balance updates only through CreditTransactions
    - Created/updated timestamps track changes
    - Monthly limit is optional (None = unlimited)
    """

    __tablename__ = "credit_ledgers"
    __table_args__ = (
        CheckConstraint('balance >= 0', name='balance_non_negative'),
        CheckConstraint('monthly_limit IS NULL OR monthly_limit >= 0', name='monthly_limit_non_negative'),
    )

    id: int = Field(
        sa_column=Column(BigInteger, primary_key=True, autoincrement=True),
        description="Unique ledger identifier (auto-increment)"
    )

    tenant_id: str = Field(
        index=True,
        unique=True,
        description="Tenant ID (unique - one ledger per tenant)"
    )

    balance: Decimal = Field(
        sa_column=Column(Numeric(18, 6), nullable=False, default=0),
        description="Current credit balance (must be >= 0, precision: 18,6)"
    )

    monthly_limit: Optional[Decimal] = Field(
        default=None,
        sa_column=Column(Numeric(18, 6), nullable=True),
        description="Optional monthly credit limit (None = unlimited)"
    )

    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Ledger creation timestamp"
    )

    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Last balance update timestamp"
    )

    class Config:
        """SQLModel configuration"""
        json_schema_extra = {
            "example": {
                "id": 1,
                "tenant_id": "tenant_xyz789",
                "balance": "1000.000000",
                "monthly_limit": "5000.000000",
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z"
            }
        }

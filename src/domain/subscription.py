"""Subscription Domain Entity

Tracks tenant subscription plans and credit allocations.
"""

from datetime import datetime, date
from decimal import Decimal
from enum import Enum
from typing import Optional
from sqlmodel import Field, Column, Index
from sqlalchemy import BigInteger, Numeric, String, Date
from src.domain.base import BaseModel


class SubscriptionStatus(str, Enum):
    """Subscription status types"""
    ACTIVE = "active"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class Subscription(BaseModel, table=True):
    """
    Subscription - Tenant subscription plan and credit allocation

    Domain Rules:
    - Each subscription allocates monthly_credits to the tenant
    - Status transitions: active -> cancelled/expired
    - end_date is optional (None = ongoing)
    - One active subscription per tenant (enforced at business logic layer)
    """

    __tablename__ = "subscriptions"
    __table_args__ = (
        Index('ix_subscriptions_tenant_id', 'tenant_id'),
        Index('ix_subscriptions_status', 'status'),
    )

    id: int = Field(
        sa_column=Column(BigInteger, primary_key=True, autoincrement=True),
        description="Unique subscription identifier (auto-increment)"
    )

    tenant_id: str = Field(
        description="Tenant ID"
    )

    status: SubscriptionStatus = Field(
        description="Subscription status (active, cancelled, expired)"
    )

    plan_name: str = Field(
        sa_column=Column(String(100), nullable=False),
        description="Name of the subscription plan"
    )

    monthly_credits: Decimal = Field(
        sa_column=Column(Numeric(18, 6), nullable=False),
        description="Monthly credit allocation (precision: 18,6)"
    )

    start_date: date = Field(
        sa_column=Column(Date, nullable=False),
        description="Subscription start date"
    )

    end_date: Optional[date] = Field(
        default=None,
        sa_column=Column(Date, nullable=True),
        description="Subscription end date (None = ongoing)"
    )

    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Subscription creation timestamp"
    )

    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Last update timestamp"
    )

    class Config:
        """SQLModel configuration"""
        json_schema_extra = {
            "example": {
                "id": 1,
                "tenant_id": "tenant_xyz789",
                "status": "active",
                "plan_name": "Pro Plan",
                "monthly_credits": "10000.000000",
                "start_date": "2024-01-01",
                "end_date": None,
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z"
            }
        }

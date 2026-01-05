"""Usage Anomaly Domain Entity

Records detected abnormal credit usage patterns for audit and alerting.
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional
from sqlmodel import Field, Column, Index
from sqlalchemy import BigInteger, Numeric, String, Text
from src.domain.base import BaseModel


class AnomalyType(str, Enum):
    """Types of usage anomalies"""
    HOURLY_THRESHOLD = "hourly_threshold"  # Exceeded hourly usage threshold
    DAILY_THRESHOLD = "daily_threshold"    # Exceeded daily usage threshold
    SPIKE = "spike"                        # Sudden usage spike (future)
    PATTERN = "pattern"                    # Unusual pattern detected (future)


class AnomalyStatus(str, Enum):
    """Anomaly resolution status"""
    DETECTED = "detected"      # Newly detected, pending review
    ACKNOWLEDGED = "acknowledged"  # Operator acknowledged
    RESOLVED = "resolved"      # Investigation completed
    FALSE_POSITIVE = "false_positive"  # Marked as false alarm


class UsageAnomaly(BaseModel, table=True):
    """
    Usage Anomaly - Records detected abnormal credit usage

    Domain Rules:
    - Each anomaly is linked to a tenant
    - Anomalies are immutable once created (except status updates)
    - Detection context stored for investigation

    Usage:
    - Background job detects anomalies and creates records
    - Operators review and update status
    - Provides audit trail for billing disputes
    """

    __tablename__ = "usage_anomalies"
    __table_args__ = (
        Index('ix_usage_anomalies_tenant_detected', 'tenant_id', 'detected_at'),
        Index('ix_usage_anomalies_status', 'status'),
    )

    id: int = Field(
        sa_column=Column(BigInteger, primary_key=True, autoincrement=True),
        description="Unique anomaly identifier (auto-increment)"
    )

    tenant_id: str = Field(
        description="Tenant that triggered the anomaly"
    )

    anomaly_type: AnomalyType = Field(
        description="Type of anomaly detected"
    )

    status: AnomalyStatus = Field(
        default=AnomalyStatus.DETECTED,
        description="Current status of the anomaly"
    )

    threshold_value: Decimal = Field(
        sa_column=Column(Numeric(18, 6), nullable=False),
        description="Threshold that was exceeded"
    )

    actual_value: Decimal = Field(
        sa_column=Column(Numeric(18, 6), nullable=False),
        description="Actual usage value that triggered anomaly"
    )

    period_start: datetime = Field(
        description="Start of the measurement period"
    )

    period_end: datetime = Field(
        description="End of the measurement period"
    )

    description: Optional[str] = Field(
        default=None,
        sa_column=Column(Text, nullable=True),
        description="Human-readable description of the anomaly"
    )

    metadata_json: Optional[str] = Field(
        default=None,
        sa_column=Column(Text, nullable=True),
        description="JSON metadata for additional context"
    )

    notified_at: Optional[datetime] = Field(
        default=None,
        description="When notification was sent (if applicable)"
    )

    resolved_at: Optional[datetime] = Field(
        default=None,
        description="When anomaly was resolved"
    )

    resolved_by: Optional[str] = Field(
        default=None,
        sa_column=Column(String(255), nullable=True),
        description="User who resolved the anomaly"
    )

    detected_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When anomaly was detected"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "id": 1,
                "tenant_id": "tenant_xyz789",
                "anomaly_type": "hourly_threshold",
                "status": "detected",
                "threshold_value": "100.000000",
                "actual_value": "150.500000",
                "period_start": "2024-01-01T10:00:00Z",
                "period_end": "2024-01-01T11:00:00Z",
                "description": "Tenant exceeded hourly credit threshold",
                "detected_at": "2024-01-01T11:05:00Z"
            }
        }

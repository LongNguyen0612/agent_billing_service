"""Unit tests for CreditTransaction domain entity"""

import pytest
from datetime import datetime
from decimal import Decimal
from pydantic import ValidationError
from src.domain.credit_transaction import CreditTransaction, TransactionType


class TestCreditTransactionCreation:
    """Test CreditTransaction entity creation with all transaction types"""

    def test_create_consume_transaction(self):
        """Test creating CONSUME transaction"""
        # Arrange
        transaction_data = {
            "tenant_id": "tenant_abc",
            "ledger_id": 1,
            "transaction_type": TransactionType.CONSUME,
            "amount": Decimal("30.500000"),
            "reference_type": "pipeline_run",
            "reference_id": "run_456",
            "idempotency_key": "pipeline_456:step_789",
            "created_at": datetime.utcnow()
        }

        # Act
        transaction = CreditTransaction(**transaction_data)

        # Assert
        assert transaction.transaction_type == TransactionType.CONSUME
        assert transaction.amount == Decimal("30.500000")
        assert transaction.reference_type == "pipeline_run"
        assert transaction.reference_id == "run_456"

    def test_create_refund_transaction(self):
        """Test creating REFUND transaction"""
        # Arrange & Act
        transaction = CreditTransaction(
            tenant_id="tenant_abc",
            ledger_id=1,
            transaction_type=TransactionType.REFUND,
            amount=Decimal("30.000000"),
            reference_type="pipeline_run",
            reference_id="run_456",
            idempotency_key="refund_tx_original_456",
            created_at=datetime.utcnow()
        )

        # Assert
        assert transaction.transaction_type == TransactionType.REFUND
        assert transaction.amount == Decimal("30.000000")

    def test_create_allocate_transaction(self):
        """Test creating ALLOCATE transaction"""
        # Arrange & Act
        transaction = CreditTransaction(
            tenant_id="tenant_abc",
            ledger_id=1,
            transaction_type=TransactionType.ALLOCATE,
            amount=Decimal("500.000000"),
            reference_type="invoice",
            reference_id="inv_001",
            idempotency_key="allocate_invoice_inv_001",
            created_at=datetime.utcnow()
        )

        # Assert
        assert transaction.transaction_type == TransactionType.ALLOCATE
        assert transaction.amount == Decimal("500.000000")

    def test_create_adjust_transaction(self):
        """Test creating ADJUST transaction"""
        # Arrange & Act
        transaction = CreditTransaction(
            tenant_id="tenant_abc",
            ledger_id=1,
            transaction_type=TransactionType.ADJUST,
            amount=Decimal("50.000000"),
            reference_type="adjustment",
            reference_id="adj_001",
            idempotency_key="admin_adjustment_2024_001",
            created_at=datetime.utcnow()
        )

        # Assert
        assert transaction.transaction_type == TransactionType.ADJUST


class TestCreditTransactionValidation:
    """Test CreditTransaction validation"""

    def test_reference_fields_are_optional(self):
        """Test that reference_type and reference_id are optional"""
        # Arrange & Act
        transaction = CreditTransaction(
            tenant_id="tenant_abc",
            ledger_id=1,
            transaction_type=TransactionType.CONSUME,
            amount=Decimal("30.000000"),
            balance_before=Decimal("100.00"),
            balance_after=Decimal("70.00"),
            idempotency_key="no_reference_tx",
            created_at=datetime.utcnow()
            # No reference_type or reference_id provided
        )

        # Assert
        assert transaction.reference_type is None
        assert transaction.reference_id is None

    def test_auto_generated_timestamp_if_not_provided(self):
        """Test that timestamp is auto-generated if not provided"""
        # Arrange & Act
        transaction = CreditTransaction(
            tenant_id="tenant_abc",
            ledger_id=1,
            transaction_type=TransactionType.CONSUME,
            amount=Decimal("30.000000"),
            balance_before=Decimal("100.00"),
            balance_after=Decimal("70.00"),
            idempotency_key="auto_timestamp_tx"
        )

        # Assert
        assert transaction.created_at is not None
        assert isinstance(transaction.created_at, datetime)

"""Unit tests for CreditLedger domain entity"""

import pytest
from datetime import datetime
from decimal import Decimal
from pydantic import ValidationError
from src.domain.credit_ledger import CreditLedger


class TestCreditLedgerCreation:
    """Test CreditLedger entity creation"""

    def test_create_credit_ledger_with_valid_data(self):
        """Test creating CreditLedger with all valid fields"""
        # Arrange
        ledger_data = {
            "tenant_id": "tenant_abc",
            "balance": Decimal("1000.000000"),
            "monthly_limit": Decimal("5000.000000"),
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }

        # Act
        ledger = CreditLedger(**ledger_data)

        # Assert
        assert ledger.tenant_id == "tenant_abc"
        assert ledger.balance == Decimal("1000.000000")
        assert ledger.monthly_limit == Decimal("5000.000000")
        assert isinstance(ledger.created_at, datetime)
        assert isinstance(ledger.updated_at, datetime)

    def test_create_credit_ledger_with_zero_balance(self):
        """Test creating CreditLedger with zero balance (valid)"""
        # Arrange & Act
        ledger = CreditLedger(
            tenant_id="tenant_abc",
            balance=Decimal("0.000000"),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

        # Assert
        assert ledger.balance == Decimal("0.000000")

    def test_create_credit_ledger_without_monthly_limit(self):
        """Test creating CreditLedger without monthly_limit (optional field)"""
        # Arrange & Act
        ledger = CreditLedger(
            tenant_id="tenant_abc",
            balance=Decimal("500.000000"),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

        # Assert
        assert ledger.monthly_limit is None


class TestCreditLedgerValidation:
    """Test CreditLedger validation rules"""

    def test_missing_required_fields_raises_validation_error(self):
        """Test that missing required fields raise validation error"""
        # Arrange
        incomplete_data = {
            "tenant_id": "tenant_abc"
            # Missing balance, created_at, updated_at
        }

        # Act & Assert
        with pytest.raises(ValidationError):
            CreditLedger(**incomplete_data)

    def test_auto_generated_timestamps_if_not_provided(self):
        """Test that timestamps are auto-generated if not provided"""
        # Arrange & Act
        ledger = CreditLedger(
            tenant_id="tenant_abc",
            balance=Decimal("500.000000")
        )

        # Assert
        assert ledger.created_at is not None
        assert ledger.updated_at is not None
        assert isinstance(ledger.created_at, datetime)
        assert isinstance(ledger.updated_at, datetime)

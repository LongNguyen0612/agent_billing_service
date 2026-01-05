"""Unit tests for ListTransactions use case (UC-36)"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime
from decimal import Decimal

from src.app.use_cases.billing.list_transactions import ListTransactions
from src.domain.credit_transaction import CreditTransaction, TransactionType


class TestListTransactions:
    """Test suite for ListTransactions use case"""

    @pytest.fixture
    def mock_transaction_repo(self):
        """Create mock credit transaction repository"""
        return AsyncMock()

    @pytest.fixture
    def use_case(self, mock_transaction_repo):
        """Create ListTransactions use case instance"""
        return ListTransactions(transaction_repo=mock_transaction_repo)

    def create_mock_transaction(
        self,
        id: int,
        tenant_id: str,
        transaction_type: TransactionType,
        amount: Decimal,
        balance_after: Decimal,
        reference_type: str = None,
        reference_id: str = None,
        created_at: datetime = None,
    ) -> MagicMock:
        """Helper to create mock transaction objects"""
        mock_txn = MagicMock(spec=CreditTransaction)
        mock_txn.id = id
        mock_txn.tenant_id = tenant_id
        mock_txn.transaction_type = transaction_type
        mock_txn.amount = amount
        mock_txn.balance_after = balance_after
        mock_txn.reference_type = reference_type
        mock_txn.reference_id = reference_id
        mock_txn.created_at = created_at or datetime.now()
        return mock_txn

    @pytest.mark.asyncio
    async def test_successful_listing_with_transactions(
        self, use_case, mock_transaction_repo
    ):
        """Test AC-2.2.1: Successful transaction list retrieval"""
        # Arrange
        tenant_id = "tenant_123"
        now = datetime(2024, 1, 15, 12, 0, 0)

        mock_transactions = [
            self.create_mock_transaction(
                id=3,
                tenant_id=tenant_id,
                transaction_type=TransactionType.CONSUME,
                amount=Decimal("-15.50"),
                balance_after=Decimal("84.50"),
                reference_type="pipeline_run",
                reference_id="run_003",
                created_at=datetime(2024, 1, 15, 12, 0, 0),
            ),
            self.create_mock_transaction(
                id=2,
                tenant_id=tenant_id,
                transaction_type=TransactionType.CONSUME,
                amount=Decimal("-25.00"),
                balance_after=Decimal("100.00"),
                reference_type="pipeline_run",
                reference_id="run_002",
                created_at=datetime(2024, 1, 14, 10, 0, 0),
            ),
            self.create_mock_transaction(
                id=1,
                tenant_id=tenant_id,
                transaction_type=TransactionType.ALLOCATE,
                amount=Decimal("125.00"),
                balance_after=Decimal("125.00"),
                reference_type="subscription",
                reference_id="sub_001",
                created_at=datetime(2024, 1, 1, 0, 0, 0),
            ),
        ]

        mock_transaction_repo.get_by_tenant_id.return_value = (mock_transactions, 3)

        # Act
        result = await use_case.execute(tenant_id)

        # Assert
        assert result.is_ok()
        response = result.value
        assert len(response.transactions) == 3
        assert response.total == 3
        assert response.limit == 20  # Default
        assert response.offset == 0  # Default

        # Verify first transaction (most recent)
        first_txn = response.transactions[0]
        assert first_txn.id == 3
        assert first_txn.transaction_type == "consume"
        assert first_txn.amount == Decimal("-15.50")
        assert first_txn.balance_after == Decimal("84.50")
        assert first_txn.reference_type == "pipeline_run"
        assert first_txn.reference_id == "run_003"

        mock_transaction_repo.get_by_tenant_id.assert_called_once_with(
            tenant_id=tenant_id, limit=20, offset=0
        )

    @pytest.mark.asyncio
    async def test_empty_transaction_list(self, use_case, mock_transaction_repo):
        """Test AC-2.2.1: Empty list when tenant has no transactions"""
        # Arrange
        tenant_id = "tenant_new"
        mock_transaction_repo.get_by_tenant_id.return_value = ([], 0)

        # Act
        result = await use_case.execute(tenant_id)

        # Assert
        assert result.is_ok()
        response = result.value
        assert len(response.transactions) == 0
        assert response.total == 0
        assert response.limit == 20
        assert response.offset == 0

        mock_transaction_repo.get_by_tenant_id.assert_called_once_with(
            tenant_id=tenant_id, limit=20, offset=0
        )

    @pytest.mark.asyncio
    async def test_pagination_with_limit(self, use_case, mock_transaction_repo):
        """Test AC-2.2.2: Pagination with custom limit"""
        # Arrange
        tenant_id = "tenant_123"
        custom_limit = 5

        mock_transactions = [
            self.create_mock_transaction(
                id=i,
                tenant_id=tenant_id,
                transaction_type=TransactionType.CONSUME,
                amount=Decimal("-10.00"),
                balance_after=Decimal("100.00"),
            )
            for i in range(5, 0, -1)
        ]

        mock_transaction_repo.get_by_tenant_id.return_value = (mock_transactions, 50)

        # Act
        result = await use_case.execute(tenant_id, limit=custom_limit)

        # Assert
        assert result.is_ok()
        response = result.value
        assert len(response.transactions) == 5
        assert response.total == 50  # Total transactions in DB
        assert response.limit == 5
        assert response.offset == 0

        mock_transaction_repo.get_by_tenant_id.assert_called_once_with(
            tenant_id=tenant_id, limit=5, offset=0
        )

    @pytest.mark.asyncio
    async def test_pagination_with_offset(self, use_case, mock_transaction_repo):
        """Test AC-2.2.2: Pagination with offset"""
        # Arrange
        tenant_id = "tenant_123"
        custom_offset = 20

        mock_transactions = [
            self.create_mock_transaction(
                id=i,
                tenant_id=tenant_id,
                transaction_type=TransactionType.CONSUME,
                amount=Decimal("-10.00"),
                balance_after=Decimal("100.00"),
            )
            for i in range(40, 20, -1)
        ]

        mock_transaction_repo.get_by_tenant_id.return_value = (mock_transactions, 150)

        # Act
        result = await use_case.execute(tenant_id, limit=20, offset=custom_offset)

        # Assert
        assert result.is_ok()
        response = result.value
        assert len(response.transactions) == 20
        assert response.total == 150
        assert response.limit == 20
        assert response.offset == 20

        mock_transaction_repo.get_by_tenant_id.assert_called_once_with(
            tenant_id=tenant_id, limit=20, offset=20
        )

    @pytest.mark.asyncio
    async def test_pagination_with_limit_and_offset(
        self, use_case, mock_transaction_repo
    ):
        """Test AC-2.2.2: Pagination with both limit and offset"""
        # Arrange
        tenant_id = "tenant_123"
        custom_limit = 10
        custom_offset = 30

        mock_transactions = [
            self.create_mock_transaction(
                id=i,
                tenant_id=tenant_id,
                transaction_type=TransactionType.CONSUME,
                amount=Decimal("-10.00"),
                balance_after=Decimal("100.00"),
            )
            for i in range(40, 30, -1)
        ]

        mock_transaction_repo.get_by_tenant_id.return_value = (mock_transactions, 100)

        # Act
        result = await use_case.execute(
            tenant_id, limit=custom_limit, offset=custom_offset
        )

        # Assert
        assert result.is_ok()
        response = result.value
        assert len(response.transactions) == 10
        assert response.total == 100
        assert response.limit == 10
        assert response.offset == 30

        mock_transaction_repo.get_by_tenant_id.assert_called_once_with(
            tenant_id=tenant_id, limit=10, offset=30
        )

    @pytest.mark.asyncio
    async def test_transaction_dto_mapping_consume(
        self, use_case, mock_transaction_repo
    ):
        """Test that consume transaction is correctly mapped to DTO"""
        # Arrange
        tenant_id = "tenant_123"
        created_at = datetime(2024, 1, 15, 14, 30, 0)

        mock_txn = self.create_mock_transaction(
            id=42,
            tenant_id=tenant_id,
            transaction_type=TransactionType.CONSUME,
            amount=Decimal("-30.500000"),
            balance_after=Decimal("969.500000"),
            reference_type="pipeline_run",
            reference_id="run_456",
            created_at=created_at,
        )

        mock_transaction_repo.get_by_tenant_id.return_value = ([mock_txn], 1)

        # Act
        result = await use_case.execute(tenant_id)

        # Assert
        assert result.is_ok()
        response = result.value
        assert len(response.transactions) == 1

        txn_dto = response.transactions[0]
        assert txn_dto.id == 42
        assert txn_dto.transaction_type == "consume"
        assert txn_dto.amount == Decimal("-30.500000")
        assert txn_dto.balance_after == Decimal("969.500000")
        assert txn_dto.reference_type == "pipeline_run"
        assert txn_dto.reference_id == "run_456"
        assert txn_dto.created_at == created_at

    @pytest.mark.asyncio
    async def test_transaction_dto_mapping_refund(
        self, use_case, mock_transaction_repo
    ):
        """Test that refund transaction is correctly mapped to DTO"""
        # Arrange
        tenant_id = "tenant_123"
        created_at = datetime(2024, 1, 15, 15, 0, 0)

        mock_txn = self.create_mock_transaction(
            id=43,
            tenant_id=tenant_id,
            transaction_type=TransactionType.REFUND,
            amount=Decimal("15.000000"),
            balance_after=Decimal("984.500000"),
            reference_type="failed_step",
            reference_id="step_789",
            created_at=created_at,
        )

        mock_transaction_repo.get_by_tenant_id.return_value = ([mock_txn], 1)

        # Act
        result = await use_case.execute(tenant_id)

        # Assert
        assert result.is_ok()
        txn_dto = result.value.transactions[0]
        assert txn_dto.id == 43
        assert txn_dto.transaction_type == "refund"
        assert txn_dto.amount == Decimal("15.000000")

    @pytest.mark.asyncio
    async def test_transaction_dto_mapping_allocate(
        self, use_case, mock_transaction_repo
    ):
        """Test that allocate transaction is correctly mapped to DTO"""
        # Arrange
        tenant_id = "tenant_123"
        created_at = datetime(2024, 1, 1, 0, 0, 0)

        mock_txn = self.create_mock_transaction(
            id=1,
            tenant_id=tenant_id,
            transaction_type=TransactionType.ALLOCATE,
            amount=Decimal("10000.000000"),
            balance_after=Decimal("10000.000000"),
            reference_type="subscription",
            reference_id="sub_001",
            created_at=created_at,
        )

        mock_transaction_repo.get_by_tenant_id.return_value = ([mock_txn], 1)

        # Act
        result = await use_case.execute(tenant_id)

        # Assert
        assert result.is_ok()
        txn_dto = result.value.transactions[0]
        assert txn_dto.id == 1
        assert txn_dto.transaction_type == "allocate"
        assert txn_dto.amount == Decimal("10000.000000")

    @pytest.mark.asyncio
    async def test_transaction_without_reference(
        self, use_case, mock_transaction_repo
    ):
        """Test transaction without reference_type and reference_id"""
        # Arrange
        tenant_id = "tenant_123"
        created_at = datetime(2024, 1, 10, 0, 0, 0)

        mock_txn = self.create_mock_transaction(
            id=10,
            tenant_id=tenant_id,
            transaction_type=TransactionType.ADJUST,
            amount=Decimal("50.000000"),
            balance_after=Decimal("1050.000000"),
            reference_type=None,
            reference_id=None,
            created_at=created_at,
        )

        mock_transaction_repo.get_by_tenant_id.return_value = ([mock_txn], 1)

        # Act
        result = await use_case.execute(tenant_id)

        # Assert
        assert result.is_ok()
        txn_dto = result.value.transactions[0]
        assert txn_dto.id == 10
        assert txn_dto.transaction_type == "adjust"
        assert txn_dto.reference_type is None
        assert txn_dto.reference_id is None

    @pytest.mark.asyncio
    async def test_multiple_transaction_types(self, use_case, mock_transaction_repo):
        """Test listing transactions with mixed transaction types"""
        # Arrange
        tenant_id = "tenant_123"

        mock_transactions = [
            self.create_mock_transaction(
                id=4,
                tenant_id=tenant_id,
                transaction_type=TransactionType.CONSUME,
                amount=Decimal("-20.00"),
                balance_after=Decimal("1030.00"),
                created_at=datetime(2024, 1, 4, 0, 0, 0),
            ),
            self.create_mock_transaction(
                id=3,
                tenant_id=tenant_id,
                transaction_type=TransactionType.REFUND,
                amount=Decimal("10.00"),
                balance_after=Decimal("1050.00"),
                created_at=datetime(2024, 1, 3, 0, 0, 0),
            ),
            self.create_mock_transaction(
                id=2,
                tenant_id=tenant_id,
                transaction_type=TransactionType.ADJUST,
                amount=Decimal("-60.00"),
                balance_after=Decimal("1040.00"),
                created_at=datetime(2024, 1, 2, 0, 0, 0),
            ),
            self.create_mock_transaction(
                id=1,
                tenant_id=tenant_id,
                transaction_type=TransactionType.ALLOCATE,
                amount=Decimal("1100.00"),
                balance_after=Decimal("1100.00"),
                created_at=datetime(2024, 1, 1, 0, 0, 0),
            ),
        ]

        mock_transaction_repo.get_by_tenant_id.return_value = (mock_transactions, 4)

        # Act
        result = await use_case.execute(tenant_id)

        # Assert
        assert result.is_ok()
        response = result.value
        assert len(response.transactions) == 4

        # Verify transaction types are correctly mapped
        assert response.transactions[0].transaction_type == "consume"
        assert response.transactions[1].transaction_type == "refund"
        assert response.transactions[2].transaction_type == "adjust"
        assert response.transactions[3].transaction_type == "allocate"

    @pytest.mark.asyncio
    async def test_large_offset_returns_empty_list(
        self, use_case, mock_transaction_repo
    ):
        """Test that offset beyond total transactions returns empty list"""
        # Arrange
        tenant_id = "tenant_123"
        mock_transaction_repo.get_by_tenant_id.return_value = ([], 50)

        # Act
        result = await use_case.execute(tenant_id, limit=20, offset=100)

        # Assert
        assert result.is_ok()
        response = result.value
        assert len(response.transactions) == 0
        assert response.total == 50  # Total still reflects actual count
        assert response.offset == 100

    @pytest.mark.asyncio
    async def test_decimal_precision_preserved(self, use_case, mock_transaction_repo):
        """Test that decimal precision is preserved in DTOs"""
        # Arrange
        tenant_id = "tenant_123"
        precise_amount = Decimal("-123.456789")
        precise_balance = Decimal("9876.543211")

        mock_txn = self.create_mock_transaction(
            id=1,
            tenant_id=tenant_id,
            transaction_type=TransactionType.CONSUME,
            amount=precise_amount,
            balance_after=precise_balance,
        )

        mock_transaction_repo.get_by_tenant_id.return_value = ([mock_txn], 1)

        # Act
        result = await use_case.execute(tenant_id)

        # Assert
        assert result.is_ok()
        txn_dto = result.value.transactions[0]
        assert txn_dto.amount == precise_amount
        assert txn_dto.balance_after == precise_balance

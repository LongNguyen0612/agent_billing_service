"""Integration tests for Billing API endpoints"""

import pytest
from datetime import datetime
from decimal import Decimal
from httpx import AsyncClient

from src.domain.credit_ledger import CreditLedger
from src.domain.credit_transaction import CreditTransaction


class TestBillingAPIIntegration:
    """Integration test suite for Billing API endpoints"""

    @pytest.mark.asyncio
    async def test_consume_credits_success(self, client: AsyncClient, db_session):
        """Test AC-1.5.1: POST /consume with valid request returns 200"""
        # Arrange - Create tenant with credits
        tenant_id = "tenant_api_consume_1"
        ledger = CreditLedger(
            tenant_id=tenant_id,
            balance=Decimal("1000.00"),
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        db_session.add(ledger)
        await db_session.commit()

        # Act - Consume credits
        payload = {
            "tenant_id": tenant_id,
            "amount": "50.00",
            "idempotency_key": "test_consume_1",
            "reference_type": "test",
            "reference_id": "test_1",
            "metadata": {"test": "data"}
        }
        response = await client.post("/billing/credits/consume", json=payload)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["tenant_id"] == tenant_id
        assert data["transaction_type"] == "consume"
        assert Decimal(data["amount"]) == Decimal("50.00")
        assert Decimal(data["balance_before"]) == Decimal("1000.00")
        assert Decimal(data["balance_after"]) == Decimal("950.00")
        assert data["idempotency_key"] == "test_consume_1"

    @pytest.mark.asyncio
    async def test_consume_credits_insufficient_balance(self, client: AsyncClient, db_session):
        """Test AC-1.5.1: POST /consume with insufficient credits returns 402"""
        # Arrange - Create tenant with low balance
        tenant_id = "tenant_api_consume_2"
        ledger = CreditLedger(
            tenant_id=tenant_id,
            balance=Decimal("10.00"),
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        db_session.add(ledger)
        await db_session.commit()

        # Act - Try to consume more than available
        payload = {
            "tenant_id": tenant_id,
            "amount": "100.00",
            "idempotency_key": "test_consume_insufficient",
        }
        response = await client.post("/billing/credits/consume", json=payload)

        # Assert
        assert response.status_code == 402
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "INSUFFICIENT_CREDIT"

    @pytest.mark.asyncio
    async def test_consume_credits_validation_error(self, client: AsyncClient):
        """Test AC-1.5.1: POST /consume with invalid request returns 400"""
        # Act - Send invalid payload (negative amount)
        payload = {
            "tenant_id": "tenant_test",
            "amount": "-50.00",
            "idempotency_key": "test_invalid",
        }
        response = await client.post("/billing/credits/consume", json=payload)

        # Assert
        assert response.status_code == 422  # Pydantic validation error

    @pytest.mark.asyncio
    async def test_consume_credits_idempotency(self, client: AsyncClient, db_session):
        """Test AC-1.5.1: Duplicate idempotency_key returns same transaction"""
        # Arrange - Create tenant
        tenant_id = "tenant_api_idempotency"
        ledger = CreditLedger(
            tenant_id=tenant_id,
            balance=Decimal("1000.00"),
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        db_session.add(ledger)
        await db_session.commit()

        # Act - Make first request
        payload = {
            "tenant_id": tenant_id,
            "amount": "50.00",
            "idempotency_key": "idempotent_key_123",
        }
        response1 = await client.post("/billing/credits/consume", json=payload)
        data1 = response1.json()

        # Make second request with same idempotency_key
        response2 = await client.post("/billing/credits/consume", json=payload)
        data2 = response2.json()

        # Assert - Both responses should be identical
        assert response1.status_code == 200
        assert response2.status_code == 200
        assert data1["transaction_id"] == data2["transaction_id"]
        assert Decimal(data2["balance_after"]) == Decimal("950.00")  # Balance only deducted once

    @pytest.mark.asyncio
    async def test_refund_credits_success(self, client: AsyncClient, db_session):
        """Test AC-1.5.2: POST /refund with valid request returns 200"""
        # Arrange - Create tenant and consume some credits first
        tenant_id = "tenant_api_refund_1"
        ledger = CreditLedger(
            tenant_id=tenant_id,
            balance=Decimal("500.00"),
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        db_session.add(ledger)
        await db_session.commit()
        await db_session.refresh(ledger)

        # Create original transaction
        original_tx = CreditTransaction(
            tenant_id=tenant_id,
            ledger_id=ledger.id,
            transaction_type="consume",
            amount=Decimal("50.00"),
            balance_before=Decimal("1000.00"),
            balance_after=Decimal("950.00"),
            idempotency_key="original_tx_1",
            created_at=datetime.now(),
        )
        db_session.add(original_tx)
        await db_session.commit()
        await db_session.refresh(original_tx)

        # Act - Refund credits
        payload = {
            "tenant_id": tenant_id,
            "amount": "30.00",
            "idempotency_key": "refund_key_1",
            "metadata": {
                "original_transaction_id": str(original_tx.id),
                "reason": "test refund"
            }
        }
        response = await client.post("/billing/credits/refund", json=payload)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["tenant_id"] == tenant_id
        assert data["transaction_type"] == "refund"
        assert Decimal(data["amount"]) == Decimal("30.00")
        assert Decimal(data["balance_after"]) == Decimal("530.00")

    @pytest.mark.asyncio
    async def test_refund_credits_validation_error(self, client: AsyncClient):
        """Test AC-1.5.2: POST /refund with invalid request returns 400"""
        # Act - Send payload without required metadata
        payload = {
            "tenant_id": "tenant_test",
            "amount": "50.00",
            "idempotency_key": "refund_invalid",
            "metadata": {}  # Missing original_transaction_id
        }
        response = await client.post("/billing/credits/refund", json=payload)

        # Assert
        assert response.status_code == 422  # Pydantic validation error

    @pytest.mark.asyncio
    async def test_get_balance_success(self, client: AsyncClient, db_session):
        """Test AC-1.5.3: GET /balance/{tenant_id} returns 200"""
        # Arrange - Create tenant with balance
        tenant_id = "tenant_api_balance_1"
        ledger = CreditLedger(
            tenant_id=tenant_id,
            balance=Decimal("1234.56"),
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        db_session.add(ledger)
        await db_session.commit()

        # Act
        response = await client.get(f"/billing/credits/balance/{tenant_id}")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["tenant_id"] == tenant_id
        assert Decimal(data["balance"]) == Decimal("1234.56")
        assert "last_updated" in data

    @pytest.mark.asyncio
    async def test_get_balance_not_found(self, client: AsyncClient):
        """Test AC-1.5.3: GET /balance/{invalid_id} returns 404"""
        # Act
        response = await client.get("/billing/credits/balance/nonexistent_tenant")

        # Assert
        assert response.status_code == 404
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "LEDGER_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_error_response_contract(self, client: AsyncClient):
        """Test AC-1.5.4: Error responses follow standard contract"""
        # Act - Trigger an error (tenant not found for balance)
        response = await client.get("/billing/credits/balance/error_test_tenant")

        # Assert - Verify error structure
        assert response.status_code == 404
        data = response.json()
        assert "error" in data
        assert "code" in data["error"]
        assert "message" in data["error"]
        assert isinstance(data["error"]["code"], str)
        assert isinstance(data["error"]["message"], str)

    @pytest.mark.asyncio
    async def test_full_workflow_consume_and_refund(self, client: AsyncClient, db_session):
        """Test full workflow: create balance, consume, check balance, refund"""
        # Arrange - Create tenant
        tenant_id = "tenant_workflow_test"
        ledger = CreditLedger(
            tenant_id=tenant_id,
            balance=Decimal("1000.00"),
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        db_session.add(ledger)
        await db_session.commit()

        # Step 1: Check initial balance
        response = await client.get(f"/billing/credits/balance/{tenant_id}")
        assert response.status_code == 200
        assert Decimal(response.json()["balance"]) == Decimal("1000.00")

        # Step 2: Consume credits
        consume_payload = {
            "tenant_id": tenant_id,
            "amount": "200.00",
            "idempotency_key": "workflow_consume_1",
        }
        response = await client.post("/billing/credits/consume", json=consume_payload)
        assert response.status_code == 200
        consume_data = response.json()
        assert Decimal(consume_data["balance_after"]) == Decimal("800.00")

        # Step 3: Check balance after consume
        response = await client.get(f"/billing/credits/balance/{tenant_id}")
        assert response.status_code == 200
        assert Decimal(response.json()["balance"]) == Decimal("800.00")

        # Step 4: Refund some credits
        refund_payload = {
            "tenant_id": tenant_id,
            "amount": "50.00",
            "idempotency_key": "workflow_refund_1",
            "metadata": {
                "original_transaction_id": str(consume_data["transaction_id"]),
                "reason": "partial refund"
            }
        }
        response = await client.post("/billing/credits/refund", json=refund_payload)
        assert response.status_code == 200
        assert Decimal(response.json()["balance_after"]) == Decimal("850.00")

        # Step 5: Verify final balance
        response = await client.get(f"/billing/credits/balance/{tenant_id}")
        assert response.status_code == 200
        assert Decimal(response.json()["balance"]) == Decimal("850.00")

    @pytest.mark.asyncio
    async def test_concurrent_consume_requests(self, client: AsyncClient, db_session):
        """Test concurrent consume requests with different idempotency keys"""
        import asyncio

        # Arrange
        tenant_id = "tenant_concurrent_api"
        ledger = CreditLedger(
            tenant_id=tenant_id,
            balance=Decimal("1000.00"),
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        db_session.add(ledger)
        await db_session.commit()

        # Act - Make concurrent requests with different idempotency keys
        async def consume(key: str, amount: str):
            payload = {
                "tenant_id": tenant_id,
                "amount": amount,
                "idempotency_key": key,
            }
            return await client.post("/billing/credits/consume", json=payload)

        responses = await asyncio.gather(
            consume("concurrent_1", "100.00"),
            consume("concurrent_2", "200.00"),
            consume("concurrent_3", "300.00"),
        )

        # Assert - All should succeed
        for response in responses:
            assert response.status_code == 200

        # Verify final balance
        response = await client.get(f"/billing/credits/balance/{tenant_id}")
        assert response.status_code == 200
        # 1000 - 100 - 200 - 300 = 400
        assert Decimal(response.json()["balance"]) == Decimal("400.00")

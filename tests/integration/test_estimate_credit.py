"""Integration tests for EstimateCredit API endpoint (UC-33)

Tests cover:
- AC-2.1.1: POST /billing/credits/estimate endpoint
- AC-2.1.2: Estimation calculation via HTTP
"""

import pytest
from decimal import Decimal
from httpx import AsyncClient


@pytest.mark.asyncio
class TestEstimateCreditEndpoint:
    """Integration tests for POST /billing/credits/estimate endpoint"""

    async def test_estimate_endpoint_with_all_known_steps(self, client: AsyncClient):
        """
        Given: Task with defined pipeline steps (all known types)
        When: POST /billing/credits/estimate is called
        Then: Estimated credit cost is returned
        And: No balance mutation occurs
        """
        # Arrange
        request_payload = {
            "task_id": "task_uuid_123",
            "pipeline_steps": ["ANALYSIS", "USER_STORIES", "CODE", "TEST"],
        }

        # Act
        response = await client.post("/billing/credits/estimate", json=request_payload)

        # Assert
        assert response.status_code == 200
        data = response.json()

        # Verify estimated_credits is correct total
        # ANALYSIS(10.0) + USER_STORIES(12.5) + CODE(15.0) + TEST(8.0) = 45.5
        # Note: Decimals are serialized as strings or floats in JSON
        assert float(data["estimated_credits"]) == 45.5

        # Verify breakdown
        breakdown = data["breakdown"]
        assert float(breakdown["ANALYSIS"]) == 10.0
        assert float(breakdown["USER_STORIES"]) == 12.5
        assert float(breakdown["CODE"]) == 15.0
        assert float(breakdown["TEST"]) == 8.0

    async def test_estimate_endpoint_with_review_and_deploy(self, client: AsyncClient):
        """Test estimation with REVIEW and DEPLOY steps"""
        # Arrange
        request_payload = {
            "task_id": "task_uuid_456",
            "pipeline_steps": ["REVIEW", "DEPLOY"],
        }

        # Act
        response = await client.post("/billing/credits/estimate", json=request_payload)

        # Assert
        assert response.status_code == 200
        data = response.json()

        # REVIEW(5.0) + DEPLOY(3.0) = 8.0
        assert float(data["estimated_credits"]) == 8.0
        assert float(data["breakdown"]["REVIEW"]) == 5.0
        assert float(data["breakdown"]["DEPLOY"]) == 3.0

    async def test_estimate_endpoint_with_unknown_steps_uses_default(self, client: AsyncClient):
        """Test that unknown step types use DEFAULT cost"""
        # Arrange
        request_payload = {
            "task_id": "task_uuid_789",
            "pipeline_steps": ["ANALYSIS", "CUSTOM_STEP", "UNKNOWN_TYPE"],
        }

        # Act
        response = await client.post("/billing/credits/estimate", json=request_payload)

        # Assert
        assert response.status_code == 200
        data = response.json()

        # ANALYSIS(10.0) + CUSTOM_STEP(5.0 default) + UNKNOWN_TYPE(5.0 default) = 20.0
        assert float(data["estimated_credits"]) == 20.0
        assert float(data["breakdown"]["ANALYSIS"]) == 10.0
        assert float(data["breakdown"]["CUSTOM_STEP"]) == 5.0
        assert float(data["breakdown"]["UNKNOWN_TYPE"]) == 5.0

    async def test_estimate_endpoint_normalizes_step_names(self, client: AsyncClient):
        """Test that step names are normalized to uppercase"""
        # Arrange
        request_payload = {
            "pipeline_steps": ["analysis", "Code", "TEST"],
        }

        # Act
        response = await client.post("/billing/credits/estimate", json=request_payload)

        # Assert
        assert response.status_code == 200
        data = response.json()

        # All keys should be uppercase in response
        breakdown = data["breakdown"]
        assert "ANALYSIS" in breakdown
        assert "CODE" in breakdown
        assert "TEST" in breakdown

        # ANALYSIS(10.0) + CODE(15.0) + TEST(8.0) = 33.0
        assert float(data["estimated_credits"]) == 33.0

    async def test_estimate_endpoint_with_empty_steps_list(self, client: AsyncClient):
        """Test estimation with empty steps list returns zero"""
        # Arrange
        request_payload = {
            "task_id": "task_empty",
            "pipeline_steps": [],
        }

        # Act
        response = await client.post("/billing/credits/estimate", json=request_payload)

        # Assert
        assert response.status_code == 200
        data = response.json()

        assert float(data["estimated_credits"]) == 0
        assert data["breakdown"] == {}

    async def test_estimate_endpoint_without_task_id(self, client: AsyncClient):
        """Test estimation works without task_id (optional field)"""
        # Arrange
        request_payload = {
            "pipeline_steps": ["CODE", "TEST"],
        }

        # Act
        response = await client.post("/billing/credits/estimate", json=request_payload)

        # Assert
        assert response.status_code == 200
        data = response.json()

        # CODE(15.0) + TEST(8.0) = 23.0
        assert float(data["estimated_credits"]) == 23.0

    async def test_estimate_endpoint_full_pipeline(self, client: AsyncClient):
        """Test estimation with full pipeline (all defined step types)"""
        # Arrange
        request_payload = {
            "task_id": "task_full_pipeline",
            "pipeline_steps": ["ANALYSIS", "USER_STORIES", "CODE", "TEST", "REVIEW", "DEPLOY"],
        }

        # Act
        response = await client.post("/billing/credits/estimate", json=request_payload)

        # Assert
        assert response.status_code == 200
        data = response.json()

        # ANALYSIS(10.0) + USER_STORIES(12.5) + CODE(15.0) + TEST(8.0) + REVIEW(5.0) + DEPLOY(3.0) = 53.5
        assert float(data["estimated_credits"]) == 53.5

        breakdown = data["breakdown"]
        assert len(breakdown) == 6
        assert float(breakdown["ANALYSIS"]) == 10.0
        assert float(breakdown["USER_STORIES"]) == 12.5
        assert float(breakdown["CODE"]) == 15.0
        assert float(breakdown["TEST"]) == 8.0
        assert float(breakdown["REVIEW"]) == 5.0
        assert float(breakdown["DEPLOY"]) == 3.0

    async def test_estimate_endpoint_response_format(self, client: AsyncClient):
        """Verify response matches the expected API contract format"""
        # Arrange
        request_payload = {
            "task_id": "task_contract_test",
            "pipeline_steps": ["ANALYSIS", "CODE"],
        }

        # Act
        response = await client.post("/billing/credits/estimate", json=request_payload)

        # Assert
        assert response.status_code == 200
        data = response.json()

        # Verify response has exactly the expected fields
        assert "estimated_credits" in data
        assert "breakdown" in data
        assert len(data) == 2  # Only these two fields

        # Verify breakdown is a dictionary
        assert isinstance(data["breakdown"], dict)

    async def test_estimate_endpoint_duplicate_steps(self, client: AsyncClient):
        """Test estimation counts duplicate steps correctly"""
        # Arrange
        request_payload = {
            "pipeline_steps": ["CODE", "CODE", "CODE"],
        }

        # Act
        response = await client.post("/billing/credits/estimate", json=request_payload)

        # Assert
        assert response.status_code == 200
        data = response.json()

        # Each CODE step costs 15.0, so total = 45.0
        assert float(data["estimated_credits"]) == 45.0


@pytest.mark.asyncio
class TestEstimateCreditEndpointValidation:
    """Test request validation for estimate endpoint"""

    async def test_estimate_endpoint_missing_pipeline_steps(self, client: AsyncClient):
        """Test that missing pipeline_steps field returns validation error"""
        # Arrange
        request_payload = {
            "task_id": "task_missing_steps",
            # Missing pipeline_steps
        }

        # Act
        response = await client.post("/billing/credits/estimate", json=request_payload)

        # Assert
        assert response.status_code == 422  # Validation error

    async def test_estimate_endpoint_invalid_pipeline_steps_type(self, client: AsyncClient):
        """Test that invalid pipeline_steps type returns validation error"""
        # Arrange
        request_payload = {
            "task_id": "task_invalid",
            "pipeline_steps": "not_a_list",  # Should be a list
        }

        # Act
        response = await client.post("/billing/credits/estimate", json=request_payload)

        # Assert
        assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
class TestEstimateCreditNoSideEffects:
    """Test that estimation has no side effects (AC-2.1.1: no balance mutation)"""

    async def test_estimate_is_idempotent(self, client: AsyncClient):
        """Test that multiple estimates return the same result"""
        # Arrange
        request_payload = {
            "task_id": "task_idempotent",
            "pipeline_steps": ["ANALYSIS", "CODE", "TEST"],
        }

        # Act - call multiple times
        response1 = await client.post("/billing/credits/estimate", json=request_payload)
        response2 = await client.post("/billing/credits/estimate", json=request_payload)
        response3 = await client.post("/billing/credits/estimate", json=request_payload)

        # Assert - all responses are identical
        assert response1.status_code == 200
        assert response2.status_code == 200
        assert response3.status_code == 200

        data1 = response1.json()
        data2 = response2.json()
        data3 = response3.json()

        assert data1["estimated_credits"] == data2["estimated_credits"] == data3["estimated_credits"]
        assert data1["breakdown"] == data2["breakdown"] == data3["breakdown"]

    async def test_estimate_does_not_require_existing_tenant(self, client: AsyncClient):
        """Test that estimation works without any existing tenant/ledger in database"""
        # Arrange - use a random task_id that has no database records
        request_payload = {
            "task_id": "nonexistent_task_xyz_12345",
            "pipeline_steps": ["ANALYSIS", "CODE"],
        }

        # Act
        response = await client.post("/billing/credits/estimate", json=request_payload)

        # Assert - estimation works without any database dependencies
        assert response.status_code == 200
        data = response.json()

        assert float(data["estimated_credits"]) == 25.0  # ANALYSIS(10) + CODE(15)

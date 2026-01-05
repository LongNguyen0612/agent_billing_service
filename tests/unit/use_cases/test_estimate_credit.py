"""Unit tests for EstimateCredit use case (UC-33)

Tests cover:
- AC-2.1.1: Estimate Calculation
- AC-2.1.2: Estimation Factors
"""

import pytest
from decimal import Decimal

from src.app.use_cases.billing.estimate_credit import EstimateCredit, STEP_COST_MATRIX
from src.app.use_cases.billing.dtos import EstimateCommandDTO


@pytest.mark.asyncio
class TestEstimateCreditSuccess:
    """Test successful credit estimation (AC-2.1.1)"""

    async def test_estimate_with_all_known_step_types(self):
        """
        Given: Task with defined pipeline steps (all known types)
        When: estimate is called
        Then: Estimated credit cost is returned with correct breakdown
        And: No balance mutation occurs (use case is stateless)
        """
        # Arrange
        use_case = EstimateCredit()
        command = EstimateCommandDTO(
            task_id="task_123",
            pipeline_steps=["ANALYSIS", "USER_STORIES", "CODE", "TEST"],
        )

        # Act
        result = await use_case.execute(command)

        # Assert
        assert result.is_ok()
        response = result.value

        # Verify breakdown
        assert response.breakdown["ANALYSIS"] == Decimal("10.0")
        assert response.breakdown["USER_STORIES"] == Decimal("12.5")
        assert response.breakdown["CODE"] == Decimal("15.0")
        assert response.breakdown["TEST"] == Decimal("8.0")

        # Verify total
        expected_total = Decimal("10.0") + Decimal("12.5") + Decimal("15.0") + Decimal("8.0")
        assert response.estimated_credits == expected_total
        assert response.estimated_credits == Decimal("45.5")

    async def test_estimate_with_review_and_deploy_steps(self):
        """Test estimation with REVIEW and DEPLOY step types"""
        # Arrange
        use_case = EstimateCredit()
        command = EstimateCommandDTO(
            task_id="task_456",
            pipeline_steps=["REVIEW", "DEPLOY"],
        )

        # Act
        result = await use_case.execute(command)

        # Assert
        assert result.is_ok()
        response = result.value

        assert response.breakdown["REVIEW"] == Decimal("5.0")
        assert response.breakdown["DEPLOY"] == Decimal("3.0")
        assert response.estimated_credits == Decimal("8.0")

    async def test_estimate_normalizes_step_names_to_uppercase(self):
        """Test that step names are normalized to uppercase"""
        # Arrange
        use_case = EstimateCredit()
        command = EstimateCommandDTO(
            task_id="task_789",
            pipeline_steps=["analysis", "Code", "TEST"],
        )

        # Act
        result = await use_case.execute(command)

        # Assert
        assert result.is_ok()
        response = result.value

        # Verify all keys are uppercase
        assert "ANALYSIS" in response.breakdown
        assert "CODE" in response.breakdown
        assert "TEST" in response.breakdown

        # Verify costs are correct
        expected_total = Decimal("10.0") + Decimal("15.0") + Decimal("8.0")
        assert response.estimated_credits == expected_total


@pytest.mark.asyncio
class TestEstimateCreditUnknownSteps:
    """Test estimation with unknown step types"""

    async def test_estimate_with_unknown_step_uses_default_cost(self):
        """
        Given: Pipeline has unknown step types
        When: Estimation is calculated
        Then: Unknown steps use DEFAULT cost (5.0)
        """
        # Arrange
        use_case = EstimateCredit()
        command = EstimateCommandDTO(
            task_id="task_unknown",
            pipeline_steps=["ANALYSIS", "CUSTOM_STEP", "UNKNOWN_TYPE"],
        )

        # Act
        result = await use_case.execute(command)

        # Assert
        assert result.is_ok()
        response = result.value

        # Known step gets its cost
        assert response.breakdown["ANALYSIS"] == Decimal("10.0")

        # Unknown steps get DEFAULT cost
        assert response.breakdown["CUSTOM_STEP"] == Decimal("5.0")
        assert response.breakdown["UNKNOWN_TYPE"] == Decimal("5.0")

        # Total is correct
        expected_total = Decimal("10.0") + Decimal("5.0") + Decimal("5.0")
        assert response.estimated_credits == expected_total

    async def test_estimate_with_only_unknown_steps(self):
        """Test estimation when all steps are unknown"""
        # Arrange
        use_case = EstimateCredit()
        command = EstimateCommandDTO(
            task_id="task_all_unknown",
            pipeline_steps=["STEP_A", "STEP_B", "STEP_C"],
        )

        # Act
        result = await use_case.execute(command)

        # Assert
        assert result.is_ok()
        response = result.value

        # All steps get DEFAULT cost
        for step in ["STEP_A", "STEP_B", "STEP_C"]:
            assert response.breakdown[step] == Decimal("5.0")

        assert response.estimated_credits == Decimal("15.0")


@pytest.mark.asyncio
class TestEstimateCreditEmptySteps:
    """Test estimation with empty steps list"""

    async def test_estimate_with_empty_steps_list(self):
        """
        Given: Pipeline has no steps
        When: Estimation is calculated
        Then: Total is zero with empty breakdown
        """
        # Arrange
        use_case = EstimateCredit()
        command = EstimateCommandDTO(
            task_id="task_empty",
            pipeline_steps=[],
        )

        # Act
        result = await use_case.execute(command)

        # Assert
        assert result.is_ok()
        response = result.value

        assert response.estimated_credits == Decimal("0")
        assert response.breakdown == {}

    async def test_estimate_without_task_id(self):
        """Test estimation works without task_id (optional field)"""
        # Arrange
        use_case = EstimateCredit()
        command = EstimateCommandDTO(
            pipeline_steps=["CODE", "TEST"],
        )

        # Act
        result = await use_case.execute(command)

        # Assert
        assert result.is_ok()
        response = result.value

        expected_total = Decimal("15.0") + Decimal("8.0")
        assert response.estimated_credits == expected_total


@pytest.mark.asyncio
class TestEstimateCreditCustomCostMatrix:
    """Test estimation with custom cost matrix (AC-2.1.2)"""

    async def test_estimate_with_custom_cost_matrix(self):
        """
        Given: Custom cost matrix is provided
        When: Estimation is calculated
        Then: Custom costs are used
        """
        # Arrange
        custom_matrix = {
            "ANALYSIS": Decimal("20.0"),
            "CODE": Decimal("30.0"),
            "DEFAULT": Decimal("10.0"),
        }
        use_case = EstimateCredit(cost_matrix=custom_matrix)
        command = EstimateCommandDTO(
            task_id="task_custom",
            pipeline_steps=["ANALYSIS", "CODE", "UNKNOWN"],
        )

        # Act
        result = await use_case.execute(command)

        # Assert
        assert result.is_ok()
        response = result.value

        assert response.breakdown["ANALYSIS"] == Decimal("20.0")
        assert response.breakdown["CODE"] == Decimal("30.0")
        assert response.breakdown["UNKNOWN"] == Decimal("10.0")  # Uses custom DEFAULT

        expected_total = Decimal("20.0") + Decimal("30.0") + Decimal("10.0")
        assert response.estimated_credits == expected_total

    async def test_estimate_custom_matrix_without_default_falls_back(self):
        """Test that custom matrix without DEFAULT uses hardcoded fallback"""
        # Arrange
        custom_matrix = {
            "ANALYSIS": Decimal("25.0"),
            # No DEFAULT key
        }
        use_case = EstimateCredit(cost_matrix=custom_matrix)
        command = EstimateCommandDTO(
            pipeline_steps=["ANALYSIS", "UNKNOWN_STEP"],
        )

        # Act
        result = await use_case.execute(command)

        # Assert
        assert result.is_ok()
        response = result.value

        assert response.breakdown["ANALYSIS"] == Decimal("25.0")
        # Falls back to hardcoded 5.0 when no DEFAULT in custom matrix
        assert response.breakdown["UNKNOWN_STEP"] == Decimal("5.0")


@pytest.mark.asyncio
class TestEstimationFactors:
    """Test estimation factor formula (AC-2.1.2)"""

    async def test_estimation_formula_is_sum_of_step_costs(self):
        """
        Given: Pipeline has N steps
        When: Estimation is calculated
        Then: estimate = sum of (cost for each step)
        """
        # Arrange
        use_case = EstimateCredit()

        # Test with different numbers of steps
        test_cases = [
            (["ANALYSIS"], Decimal("10.0")),
            (["ANALYSIS", "CODE"], Decimal("25.0")),
            (["ANALYSIS", "USER_STORIES", "CODE"], Decimal("37.5")),
            (["ANALYSIS", "USER_STORIES", "CODE", "TEST"], Decimal("45.5")),
            (["ANALYSIS", "USER_STORIES", "CODE", "TEST", "REVIEW"], Decimal("50.5")),
            (["ANALYSIS", "USER_STORIES", "CODE", "TEST", "REVIEW", "DEPLOY"], Decimal("53.5")),
        ]

        for steps, expected_total in test_cases:
            command = EstimateCommandDTO(pipeline_steps=steps)

            # Act
            result = await use_case.execute(command)

            # Assert
            assert result.is_ok()
            assert result.value.estimated_credits == expected_total, (
                f"Failed for steps {steps}: expected {expected_total}, got {result.value.estimated_credits}"
            )

    async def test_duplicate_steps_are_counted_multiple_times(self):
        """Test that duplicate steps are each counted in the total"""
        # Arrange
        use_case = EstimateCredit()
        command = EstimateCommandDTO(
            pipeline_steps=["CODE", "CODE", "CODE"],
        )

        # Act
        result = await use_case.execute(command)

        # Assert
        assert result.is_ok()
        response = result.value

        # Note: The current implementation will overwrite duplicate keys in breakdown
        # Each CODE step costs 15.0, but breakdown dict will only have one entry
        # Total should be 15.0 * 3 = 45.0
        assert response.estimated_credits == Decimal("45.0")

    async def test_default_cost_matrix_values_match_expected(self):
        """Verify the default cost matrix has expected values"""
        # These are the expected costs based on the implementation
        expected = {
            "ANALYSIS": Decimal("10.0"),
            "USER_STORIES": Decimal("12.5"),
            "CODE": Decimal("15.0"),
            "TEST": Decimal("8.0"),
            "REVIEW": Decimal("5.0"),
            "DEPLOY": Decimal("3.0"),
            "DEFAULT": Decimal("5.0"),
        }

        for step, expected_cost in expected.items():
            assert STEP_COST_MATRIX[step] == expected_cost, (
                f"Step {step}: expected {expected_cost}, got {STEP_COST_MATRIX[step]}"
            )


@pytest.mark.asyncio
class TestEstimateCreditStateless:
    """Test that estimation is a read-only operation"""

    async def test_estimation_does_not_require_database(self):
        """
        Given: No database connection or repositories
        When: Estimation is calculated
        Then: Estimation succeeds (no external dependencies)
        """
        # Arrange - no mocks or database needed
        use_case = EstimateCredit()
        command = EstimateCommandDTO(
            task_id="task_stateless",
            pipeline_steps=["ANALYSIS", "CODE"],
        )

        # Act
        result = await use_case.execute(command)

        # Assert
        assert result.is_ok()
        assert result.value.estimated_credits == Decimal("25.0")

    async def test_multiple_estimations_are_independent(self):
        """Test that multiple estimations don't affect each other"""
        # Arrange
        use_case = EstimateCredit()

        command1 = EstimateCommandDTO(
            task_id="task_1",
            pipeline_steps=["ANALYSIS"],
        )
        command2 = EstimateCommandDTO(
            task_id="task_2",
            pipeline_steps=["CODE", "TEST"],
        )

        # Act
        result1 = await use_case.execute(command1)
        result2 = await use_case.execute(command2)

        # Assert - results are independent
        assert result1.is_ok()
        assert result2.is_ok()

        assert result1.value.estimated_credits == Decimal("10.0")
        assert result2.value.estimated_credits == Decimal("23.0")

        # Breakdown should be independent
        assert "ANALYSIS" in result1.value.breakdown
        assert "ANALYSIS" not in result2.value.breakdown
        assert "CODE" in result2.value.breakdown
        assert "CODE" not in result1.value.breakdown

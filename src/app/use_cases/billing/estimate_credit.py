"""
Estimate Credit Use Case (UC-33)

Calculates estimated credit cost for pipeline execution without mutating balance.
"""
from decimal import Decimal
from libs.result import Result, Return
from .dtos import EstimateCommandDTO, EstimateResponseDTO


# Cost matrix for pipeline step types
# These values should be configurable in production
STEP_COST_MATRIX: dict[str, Decimal] = {
    "ANALYSIS": Decimal("10.0"),
    "USER_STORIES": Decimal("12.5"),
    "CODE": Decimal("15.0"),
    "TEST": Decimal("8.0"),
    "REVIEW": Decimal("5.0"),
    "DEPLOY": Decimal("3.0"),
    # Default cost for unknown step types
    "DEFAULT": Decimal("5.0"),
}


class EstimateCredit:
    """
    Use case: Preflight Credit Estimation (UC-33)

    Calculates the estimated credit cost for a pipeline execution
    based on the defined step types. This is a read-only operation
    that does not mutate any balance.
    """

    def __init__(self, cost_matrix: dict[str, Decimal] = None):
        """
        Initialize with optional custom cost matrix.

        Args:
            cost_matrix: Optional custom cost matrix. Defaults to STEP_COST_MATRIX.
        """
        self.cost_matrix = cost_matrix or STEP_COST_MATRIX

    async def execute(self, command: EstimateCommandDTO) -> Result[EstimateResponseDTO]:
        """
        Calculate estimated credit cost for pipeline steps.

        Args:
            command: Estimate command with pipeline steps

        Returns:
            Result[EstimateResponseDTO]: Estimated cost breakdown
        """
        breakdown: dict[str, Decimal] = {}
        total_cost = Decimal("0")

        for step in command.pipeline_steps:
            # Normalize step name to uppercase
            step_upper = step.upper()

            # Get cost from matrix or use default
            step_cost = self.cost_matrix.get(step_upper, self.cost_matrix.get("DEFAULT", Decimal("5.0")))

            breakdown[step_upper] = step_cost
            total_cost += step_cost

        return Return.ok(
            EstimateResponseDTO(
                estimated_credits=total_cost,
                breakdown=breakdown,
            )
        )

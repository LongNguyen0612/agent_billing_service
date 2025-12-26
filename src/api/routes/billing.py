"""Billing API Routes

FastAPI routes for credit management operations.
"""

from fastapi import APIRouter, Depends, status
from sqlmodel.ext.asyncio.session import AsyncSession

from src.api.schemas.billing_request import ConsumeRequestSchema, RefundRequestSchema
from src.app.use_cases.billing.dtos import (
    CreditTransactionResponseDTO,
    BalanceResponseDTO,
    ConsumeCommandDTO,
    RefundCommandDTO,
)
from src.app.use_cases.billing.consume_credit import ConsumeCredit
from src.app.use_cases.billing.refund_credit import RefundCredit
from src.app.use_cases.billing.get_balance import GetBalance
from src.adapter.repositories.credit_ledger_repository import CreditLedgerRepository
from src.adapter.repositories.credit_transaction_repository import CreditTransactionRepository
from src.adapter.services.unit_of_work import SqlAlchemyUnitOfWork
from src.depends import get_session
from src.api.error import ClientError

router = APIRouter(prefix="/billing/credits", tags=["Billing"])


@router.post(
    "/consume",
    response_model=CreditTransactionResponseDTO,
    status_code=status.HTTP_200_OK,
    responses={
        402: {
            "description": "Insufficient credits",
            "content": {
                "application/json": {
                    "example": {
                        "error": {
                            "code": "INSUFFICIENT_CREDIT",
                            "message": "Insufficient credits. Required: 100.00, Available: 50.00"
                        }
                    }
                }
            }
        },
        400: {
            "description": "Validation error",
            "content": {
                "application/json": {
                    "example": {
                        "error": {
                            "code": "VALIDATION_ERROR",
                            "message": "Invalid request parameters"
                        }
                    }
                }
            }
        }
    }
)
async def consume_credits(
    request: ConsumeRequestSchema,
    session: AsyncSession = Depends(get_session)
):
    """
    Consume credits from tenant balance with idempotency guarantee.

    This endpoint deducts credits from a tenant's balance. It provides strong
    idempotency guarantees - repeated requests with the same idempotency_key
    will return the same transaction without double-charging.

    **Request body:**
    - `tenant_id` (required): Tenant identifier
    - `amount` (required): Credit amount to consume (must be > 0)
    - `idempotency_key` (required): Unique key for idempotent operations
    - `reference_type` (optional): Type of reference (e.g., 'pipeline_run')
    - `reference_id` (optional): ID of referenced entity
    - `metadata` (optional): Additional metadata for audit trail

    **Example request:**
    ```json
    {
      "tenant_id": "tenant_xyz789",
      "amount": "30.50",
      "idempotency_key": "pipeline_456:step_789",
      "reference_type": "pipeline_run",
      "reference_id": "run_456",
      "metadata": {"model": "gpt-4", "tokens": 1500}
    }
    ```

    **Returns:**
    - 200: Credit consumed successfully
    - 402: Insufficient credits available
    - 400: Invalid request parameters
    """
    # Create UnitOfWork and repositories
    uow = SqlAlchemyUnitOfWork(session)
    ledger_repo = CreditLedgerRepository(session)
    transaction_repo = CreditTransactionRepository(session)

    # Convert request schema to command DTO
    command = ConsumeCommandDTO(
        tenant_id=request.tenant_id,
        amount=request.amount,
        idempotency_key=request.idempotency_key,
        reference_type=request.reference_type,
        reference_id=request.reference_id,
        metadata=request.metadata,
    )

    # Execute use case
    use_case = ConsumeCredit(uow, ledger_repo, transaction_repo)
    result = await use_case.execute(command)

    # Handle errors
    if result.is_err():
        if result.error.code == "INSUFFICIENT_CREDIT":
            raise ClientError(result.error, status_code=status.HTTP_402_PAYMENT_REQUIRED)
        raise ClientError(result.error)

    # Return successful response
    return result.value


@router.post(
    "/refund",
    response_model=CreditTransactionResponseDTO,
    status_code=status.HTTP_200_OK,
    responses={
        400: {
            "description": "Validation error",
            "content": {
                "application/json": {
                    "example": {
                        "error": {
                            "code": "VALIDATION_ERROR",
                            "message": "Invalid request parameters"
                        }
                    }
                }
            }
        }
    }
)
async def refund_credits(
    request: RefundRequestSchema,
    session: AsyncSession = Depends(get_session)
):
    """
    Refund credits back to tenant balance.

    This endpoint adds credits back to a tenant's balance, typically used
    for compensation when operations fail. Like consume, it provides
    idempotency guarantees.

    **Request body:**
    - `tenant_id` (required): Tenant identifier
    - `amount` (required): Credit amount to refund (must be > 0)
    - `idempotency_key` (required): Unique key for idempotent operations
    - `reference_type` (optional): Type of reference
    - `reference_id` (optional): ID of referenced entity
    - `metadata` (required): Must include original_transaction_id and reason

    **Example request:**
    ```json
    {
      "tenant_id": "tenant_xyz789",
      "amount": "30.50",
      "idempotency_key": "refund:pipeline_456:step_789",
      "reference_type": "failed_step",
      "reference_id": "step_789",
      "metadata": {
        "original_transaction_id": "123",
        "pipeline_run_id": "run_456",
        "reason": "AI service timeout"
      }
    }
    ```

    **Returns:**
    - 200: Credits refunded successfully
    - 400: Invalid request parameters
    """
    # Create UnitOfWork and repositories
    uow = SqlAlchemyUnitOfWork(session)
    ledger_repo = CreditLedgerRepository(session)
    transaction_repo = CreditTransactionRepository(session)

    # Convert request schema to command DTO
    command = RefundCommandDTO(
        tenant_id=request.tenant_id,
        amount=request.amount,
        idempotency_key=request.idempotency_key,
        reference_type=request.reference_type,
        reference_id=request.reference_id,
        metadata=request.metadata,
    )

    # Execute use case
    use_case = RefundCredit(uow, ledger_repo, transaction_repo)
    result = await use_case.execute(command)

    # Handle errors
    if result.is_err():
        raise ClientError(result.error)

    # Return successful response
    return result.value


@router.get(
    "/balance/{tenant_id}",
    response_model=BalanceResponseDTO,
    status_code=status.HTTP_200_OK,
    responses={
        404: {
            "description": "Tenant ledger not found",
            "content": {
                "application/json": {
                    "example": {
                        "error": {
                            "code": "LEDGER_NOT_FOUND",
                            "message": "No credit ledger found for tenant tenant_123"
                        }
                    }
                }
            }
        }
    }
)
async def get_balance(
    tenant_id: str,
    session: AsyncSession = Depends(get_session)
):
    """
    Get current credit balance for a tenant.

    This is a read-only operation that retrieves the current credit balance
    and last update timestamp for a given tenant.

    **Path parameters:**
    - `tenant_id` (required): Tenant identifier

    **Example response:**
    ```json
    {
      "tenant_id": "tenant_xyz789",
      "balance": "969.50",
      "last_updated": "2024-01-01T00:00:00Z"
    }
    ```

    **Returns:**
    - 200: Balance retrieved successfully
    - 404: Tenant ledger not found
    """
    # Create repository
    ledger_repo = CreditLedgerRepository(session)

    # Execute use case
    use_case = GetBalance(ledger_repo)
    result = await use_case.execute(tenant_id)

    # Handle errors
    if result.is_err():
        if result.error.code == "LEDGER_NOT_FOUND":
            raise ClientError(result.error, status_code=status.HTTP_404_NOT_FOUND)
        raise ClientError(result.error)

    # Return successful response
    return result.value

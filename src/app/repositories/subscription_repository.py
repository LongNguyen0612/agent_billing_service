"""Subscription Repository Interface

Defines the contract for subscription persistence operations.
"""

from abc import ABC, abstractmethod
from typing import Optional, List
from src.domain.subscription import Subscription, SubscriptionStatus


class SubscriptionRepository(ABC):
    """
    Repository interface for Subscription persistence

    Provides access to tenant subscription data for credit allocation.
    """

    @abstractmethod
    async def get_by_tenant_id(
        self, tenant_id: str, status: Optional[SubscriptionStatus] = None
    ) -> Optional[Subscription]:
        """
        Retrieve subscription by tenant ID

        Args:
            tenant_id: Tenant identifier
            status: Optional filter by status (e.g., ACTIVE)

        Returns:
            Subscription if found, None otherwise
        """
        pass

    @abstractmethod
    async def get_active_subscriptions(self) -> List[Subscription]:
        """
        Retrieve all active subscriptions

        Used by monthly allocation job to process all tenants.

        Returns:
            List of active subscriptions
        """
        pass

    @abstractmethod
    async def create(self, subscription: Subscription) -> Subscription:
        """
        Create a new subscription

        Args:
            subscription: Subscription entity to persist

        Returns:
            Created Subscription with generated ID
        """
        pass

    @abstractmethod
    async def update(self, subscription: Subscription) -> Subscription:
        """
        Update an existing subscription

        Args:
            subscription: Subscription entity with updated values

        Returns:
            Updated Subscription
        """
        pass

    @abstractmethod
    async def get_by_id(self, subscription_id: int) -> Optional[Subscription]:
        """
        Retrieve subscription by ID

        Args:
            subscription_id: Subscription ID

        Returns:
            Subscription if found, None otherwise
        """
        pass

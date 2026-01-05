"""SQLAlchemy Subscription Repository Implementation

Implements subscription persistence using SQLAlchemy async session.
"""

from typing import Optional, List
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from src.app.repositories.subscription_repository import SubscriptionRepository
from src.domain.subscription import Subscription, SubscriptionStatus


class SqlAlchemySubscriptionRepository(SubscriptionRepository):
    """
    SQLAlchemy implementation of SubscriptionRepository

    Uses async session for database operations.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_tenant_id(
        self, tenant_id: str, status: Optional[SubscriptionStatus] = None
    ) -> Optional[Subscription]:
        """
        Retrieve subscription by tenant ID

        Args:
            tenant_id: Tenant identifier
            status: Optional filter by status

        Returns:
            Subscription if found, None otherwise
        """
        statement = select(Subscription).where(Subscription.tenant_id == tenant_id)

        if status:
            statement = statement.where(Subscription.status == status)

        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_active_subscriptions(self) -> List[Subscription]:
        """
        Retrieve all active subscriptions

        Returns:
            List of active subscriptions
        """
        statement = select(Subscription).where(
            Subscription.status == SubscriptionStatus.ACTIVE
        )
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def create(self, subscription: Subscription) -> Subscription:
        """
        Create a new subscription

        Args:
            subscription: Subscription entity to persist

        Returns:
            Created Subscription with generated ID
        """
        self.session.add(subscription)
        await self.session.flush()
        await self.session.refresh(subscription)
        return subscription

    async def update(self, subscription: Subscription) -> Subscription:
        """
        Update an existing subscription

        Args:
            subscription: Subscription entity with updated values

        Returns:
            Updated Subscription
        """
        self.session.add(subscription)
        await self.session.flush()
        await self.session.refresh(subscription)
        return subscription

    async def get_by_id(self, subscription_id: int) -> Optional[Subscription]:
        """
        Retrieve subscription by ID

        Args:
            subscription_id: Subscription ID

        Returns:
            Subscription if found, None otherwise
        """
        statement = select(Subscription).where(Subscription.id == subscription_id)
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

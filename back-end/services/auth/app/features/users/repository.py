import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from services.auth.app.features.users.models import RefreshTokenModel, UserModel


class UsersRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, user_id: uuid.UUID) -> UserModel | None:
        query = select(UserModel).where(UserModel.id == user_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> UserModel | None:
        query = select(UserModel).where(UserModel.email == email.lower())
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def create_user(self, email: str, password_hash: str, name: str) -> UserModel:
        user = UserModel(
            email=email.lower(),
            password_hash=password_hash,
            name=name,
        )
        self.session.add(user)
        await self.session.flush()
        return user

    async def update_user(self, user: UserModel, **kwargs) -> UserModel:
        for key, value in kwargs.items():
            if value is not None or key == "avatar_media_id":
                setattr(user, key, value)
        await self.session.flush()
        return user

    async def search_users(
        self, query_str: str, exclude_user_id: uuid.UUID | None = None
    ) -> Sequence[UserModel]:
        pattern = f"%{query_str.lower()}%"
        stmt = select(UserModel).where(
            or_(
                UserModel.email.ilike(pattern),
                UserModel.name.ilike(pattern),
            ),
            UserModel.is_active.is_(True),
        )
        if exclude_user_id:
            stmt = stmt.where(UserModel.id != exclude_user_id)
        stmt = stmt.limit(20)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_by_ids(self, user_ids: set[uuid.UUID]) -> Sequence[UserModel]:
        if not user_ids:
            return []
        stmt = select(UserModel).where(UserModel.id.in_(user_ids))
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def save_refresh_token(
        self, user_id: uuid.UUID, token_hash: str, expires_at: datetime
    ) -> RefreshTokenModel:
        token_record = RefreshTokenModel(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        self.session.add(token_record)
        await self.session.flush()
        return token_record

    async def get_refresh_token(self, token_hash: str) -> RefreshTokenModel | None:
        stmt = select(RefreshTokenModel).where(
            RefreshTokenModel.token_hash == token_hash
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def revoke_refresh_token(self, token_hash: str) -> bool:
        record = await self.get_refresh_token(token_hash)
        if record and record.revoked_at is None:
            record.revoked_at = datetime.now(UTC)
            await self.session.flush()
            return True
        return False

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from services.auth.app.core.config import settings
from services.auth.app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_token,
    verify_password,
)
from services.auth.app.features.users.models import UserModel
from services.auth.app.features.users.repository import UsersRepository
from services.auth.app.features.users.schemas import (
    AuthTokenResponse,
    UserRead,
    UserRegisterRequest,
    UserSummary,
    UserUpdateRequest,
)


class EmailAlreadyExistsError(Exception):
    def __init__(self, email: str) -> None:
        super().__init__(f"Email '{email}' đã được đăng ký.")
        self.email = email


class InvalidCredentialsError(Exception):
    def __init__(self) -> None:
        super().__init__("Email hoặc mật khẩu không chính xác.")


class InvalidRefreshTokenError(Exception):
    def __init__(
        self, message: str = "Refresh token không hợp lệ hoặc đã hết hạn."
    ) -> None:
        super().__init__(message)


class UserNotFoundError(Exception):
    def __init__(self, user_id: uuid.UUID) -> None:
        super().__init__(f"Không tìm thấy người dùng với ID '{user_id}'.")
        self.user_id = user_id


class UsersService:
    def __init__(self, session: AsyncSession) -> None:
        self.repo = UsersRepository(session)
        self.session = session

    async def register(self, req: UserRegisterRequest) -> AuthTokenResponse:
        existing = await self.repo.get_by_email(req.email)
        if existing:
            raise EmailAlreadyExistsError(req.email)

        pwd_hash = hash_password(req.password)
        user = await self.repo.create_user(
            email=req.email,
            password_hash=pwd_hash,
            name=req.name,
        )

        tokens = await self._issue_tokens(user)
        await self.session.commit()
        return tokens

    async def login(self, email: str, password: str) -> AuthTokenResponse:
        user = await self.repo.get_by_email(email)
        if not user or not user.is_active:
            raise InvalidCredentialsError()

        if not verify_password(password, user.password_hash):
            raise InvalidCredentialsError()

        tokens = await self._issue_tokens(user)
        await self.session.commit()
        return tokens

    async def refresh_tokens(self, plain_refresh_token: str) -> AuthTokenResponse:
        token_hash = hash_token(plain_refresh_token)
        token_record = await self.repo.get_refresh_token(token_hash)

        if not token_record:
            raise InvalidRefreshTokenError("Refresh token không tồn tại.")

        if token_record.revoked_at is not None:
            raise InvalidRefreshTokenError("Refresh token đã bị thu hồi.")

        now = datetime.now(UTC)
        if token_record.expires_at < now:
            raise InvalidRefreshTokenError("Refresh token đã hết hạn.")

        user = await self.repo.get_by_id(token_record.user_id)
        if not user or not user.is_active:
            raise InvalidRefreshTokenError("Tài khoản người dùng không còn hoạt động.")

        # Revoke old refresh token (Token Rotation)
        await self.repo.revoke_refresh_token(token_hash)

        # Issue new token pair
        tokens = await self._issue_tokens(user)
        await self.session.commit()
        return tokens

    async def logout(self, plain_refresh_token: str) -> None:
        token_hash = hash_token(plain_refresh_token)
        await self.repo.revoke_refresh_token(token_hash)
        await self.session.commit()

    async def get_user_profile(self, user_id: uuid.UUID) -> UserRead:
        user = await self.repo.get_by_id(user_id)
        if not user:
            raise UserNotFoundError(user_id)
        return UserRead.model_validate(user)

    async def update_user_profile(
        self, user_id: uuid.UUID, req: UserUpdateRequest
    ) -> UserRead:
        user = await self.repo.get_by_id(user_id)
        if not user:
            raise UserNotFoundError(user_id)

        update_data = req.model_dump(exclude_unset=True)
        user = await self.repo.update_user(user, **update_data)
        await self.session.commit()
        return UserRead.model_validate(user)

    async def search_users(
        self, query_str: str, exclude_user_id: uuid.UUID | None = None
    ) -> list[UserSummary]:
        if len(query_str.strip()) < 2:
            return []
        users = await self.repo.search_users(query_str, exclude_user_id=exclude_user_id)
        return [UserSummary.model_validate(u) for u in users]

    async def get_users_batch(self, user_ids: set[uuid.UUID]) -> dict[str, UserSummary]:
        users = await self.repo.get_by_ids(user_ids)
        return {str(u.id): UserSummary.model_validate(u) for u in users}

    async def _issue_tokens(self, user: UserModel) -> AuthTokenResponse:
        access_token = create_access_token(
            data={"sub": str(user.id), "email": user.email}
        )
        refresh_token = generate_refresh_token()
        refresh_hash = hash_token(refresh_token)
        expires_at = datetime.now(UTC) + timedelta(
            days=settings.REFRESH_TOKEN_EXPIRE_DAYS
        )

        await self.repo.save_refresh_token(
            user_id=user.id,
            token_hash=refresh_hash,
            expires_at=expires_at,
        )

        return AuthTokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=UserRead.model_validate(user),
        )

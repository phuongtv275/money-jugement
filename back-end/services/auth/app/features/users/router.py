import uuid

import jwt
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from services.auth.app.core.database import get_db
from services.auth.app.core.security import decode_access_token
from services.auth.app.features.users.schemas import (
    AuthTokenResponse,
    MessageResponse,
    RefreshTokenRequest,
    UserLoginRequest,
    UserRead,
    UserRegisterRequest,
    UserSummary,
    UserUpdateRequest,
)
from services.auth.app.features.users.service import (
    EmailAlreadyExistsError,
    InvalidCredentialsError,
    InvalidRefreshTokenError,
    UserNotFoundError,
    UsersService,
)

router = APIRouter()


async def get_current_user_id(
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> uuid.UUID:
    if x_user_id:
        try:
            return uuid.UUID(x_user_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "error_code": "INVALID_TOKEN",
                    "message": "X-User-Id header không hợp lệ.",
                },
            )

    if authorization and authorization.startswith("Bearer "):
        token = authorization.removeprefix("Bearer ").strip()
        try:
            payload = decode_access_token(token)
            sub = payload.get("sub")
            if not sub:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail={
                        "error_code": "INVALID_TOKEN",
                        "message": "Token không chứa user id.",
                    },
                )
            return uuid.UUID(sub)
        except (jwt.PyJWTError, ValueError):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "error_code": "INVALID_TOKEN",
                    "message": "Access token không hợp lệ hoặc đã hết hạn.",
                },
            )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={
            "error_code": "UNAUTHORIZED",
            "message": "Yêu cầu đăng nhập hoặc thiếu thông tin định danh.",
        },
    )


# --- AUTH ENDPOINTS ---


@router.post(
    "/auth/register",
    response_model=AuthTokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Đăng ký tài khoản mới",
)
async def register(
    req: UserRegisterRequest,
    session: AsyncSession = Depends(get_db),
) -> AuthTokenResponse:
    service = UsersService(session)
    try:
        return await service.register(req)
    except EmailAlreadyExistsError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error_code": "EMAIL_ALREADY_EXISTS", "message": str(e)},
        )


@router.post(
    "/auth/login",
    response_model=AuthTokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Đăng nhập tài khoản",
)
async def login(
    req: UserLoginRequest,
    session: AsyncSession = Depends(get_db),
) -> AuthTokenResponse:
    service = UsersService(session)
    try:
        return await service.login(req.email, req.password)
    except InvalidCredentialsError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error_code": "INVALID_CREDENTIALS", "message": str(e)},
        )


@router.post(
    "/auth/refresh",
    response_model=AuthTokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Cấp mới token bằng refresh token",
)
async def refresh_tokens(
    req: RefreshTokenRequest,
    session: AsyncSession = Depends(get_db),
) -> AuthTokenResponse:
    service = UsersService(session)
    try:
        return await service.refresh_tokens(req.refresh_token)
    except InvalidRefreshTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error_code": "INVALID_REFRESH_TOKEN", "message": str(e)},
        )


@router.post(
    "/auth/logout",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Đăng xuất và thu hồi refresh token",
)
async def logout(
    req: RefreshTokenRequest,
    session: AsyncSession = Depends(get_db),
) -> MessageResponse:
    service = UsersService(session)
    await service.logout(req.refresh_token)
    return MessageResponse(message="Đăng xuất thành công.")


# --- USERS PROFILE & DIRECTORY ---


@router.get(
    "/users/me",
    response_model=UserRead,
    status_code=status.HTTP_200_OK,
    summary="Lấy thông tin cá nhân",
)
async def get_current_user_profile(
    current_user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
) -> UserRead:
    service = UsersService(session)
    try:
        return await service.get_user_profile(current_user_id)
    except UserNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "USER_NOT_FOUND", "message": str(e)},
        )


@router.patch(
    "/users/me",
    response_model=UserRead,
    status_code=status.HTTP_200_OK,
    summary="Cập nhật thông tin cá nhân & ngân hàng",
)
async def update_current_user_profile(
    req: UserUpdateRequest,
    current_user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
) -> UserRead:
    service = UsersService(session)
    try:
        return await service.update_user_profile(current_user_id, req)
    except UserNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "USER_NOT_FOUND", "message": str(e)},
        )


@router.get(
    "/users/search",
    response_model=list[UserSummary],
    status_code=status.HTTP_200_OK,
    summary="Tìm kiếm người dùng",
)
async def search_users(
    query: str = Query(..., min_length=2, description="Từ khóa email hoặc tên"),
    current_user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
) -> list[UserSummary]:
    service = UsersService(session)
    return await service.search_users(query, exclude_user_id=current_user_id)


@router.get(
    "/internal/users/batch",
    response_model=dict[str, UserSummary],
    status_code=status.HTTP_200_OK,
    summary="Endpoint nội bộ lấy batch thông tin người dùng",
)
async def get_users_batch(
    ids: list[uuid.UUID] = Query(default=[], description="Danh sách User ID cần lấy"),
    session: AsyncSession = Depends(get_db),
) -> dict[str, UserSummary]:
    service = UsersService(session)
    return await service.get_users_batch(set(ids))

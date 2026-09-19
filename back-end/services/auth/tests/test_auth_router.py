import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_register_success(client: AsyncClient):
    payload = {
        "email": "nam.nguyen@example.com",
        "password": "Password123!",
        "name": "Nguyễn Văn Nam",
    }
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "nam.nguyen@example.com"
    assert data["user"]["name"] == "Nguyễn Văn Nam"
    assert data["user"]["is_active"] is True


async def test_register_duplicate_email(client: AsyncClient):
    payload = {
        "email": "nam.nguyen@example.com",
        "password": "Password123!",
        "name": "Nguyễn Văn Nam",
    }
    resp1 = await client.post("/api/v1/auth/register", json=payload)
    assert resp1.status_code == 201

    resp2 = await client.post("/api/v1/auth/register", json=payload)
    assert resp2.status_code == 409
    data = resp2.json()
    assert data["detail"]["error_code"] == "EMAIL_ALREADY_EXISTS"


async def test_login_success(client: AsyncClient):
    reg_payload = {
        "email": "login.user@example.com",
        "password": "SecretPassword123",
        "name": "Login User",
    }
    await client.post("/api/v1/auth/register", json=reg_payload)

    login_payload = {
        "email": "login.user@example.com",
        "password": "SecretPassword123",
    }
    resp = await client.post("/api/v1/auth/login", json=login_payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["user"]["email"] == "login.user@example.com"


async def test_login_invalid_credentials(client: AsyncClient):
    reg_payload = {
        "email": "valid.user@example.com",
        "password": "CorrectPassword123",
        "name": "Valid User",
    }
    await client.post("/api/v1/auth/register", json=reg_payload)

    # Wrong password
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "valid.user@example.com", "password": "WrongPassword"},
    )
    assert resp.status_code == 401
    assert resp.json()["detail"]["error_code"] == "INVALID_CREDENTIALS"

    # Non-existent email
    resp_no_email = await client.post(
        "/api/v1/auth/login",
        json={"email": "nonexistent@example.com", "password": "AnyPassword"},
    )
    assert resp_no_email.status_code == 401
    assert resp_no_email.json()["detail"]["error_code"] == "INVALID_CREDENTIALS"


async def test_refresh_token_rotation_and_revocation(client: AsyncClient):
    reg_resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "refresh.user@example.com",
            "password": "Password123",
            "name": "Refresh User",
        },
    )
    tokens = reg_resp.json()
    old_refresh_token = tokens["refresh_token"]

    # 1. Refreshing with valid refresh token succeeds
    refresh_resp = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": old_refresh_token},
    )
    assert refresh_resp.status_code == 200
    new_tokens = refresh_resp.json()
    assert "access_token" in new_tokens
    assert new_tokens["refresh_token"] != old_refresh_token

    # 2. Reusing old refresh token must be rejected (Token Rotation)
    stale_resp = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": old_refresh_token},
    )
    assert stale_resp.status_code == 401
    assert stale_resp.json()["detail"]["error_code"] == "INVALID_REFRESH_TOKEN"


async def test_logout_revokes_refresh_token(client: AsyncClient):
    reg_resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "logout.user@example.com",
            "password": "Password123",
            "name": "Logout User",
        },
    )
    refresh_token = reg_resp.json()["refresh_token"]

    # Logout
    logout_resp = await client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": refresh_token},
    )
    assert logout_resp.status_code == 200
    assert logout_resp.json()["message"] == "Đăng xuất thành công."

    # Using revoked refresh token fails
    refresh_resp = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert refresh_resp.status_code == 401
    assert refresh_resp.json()["detail"]["error_code"] == "INVALID_REFRESH_TOKEN"


async def test_user_profile_and_bank_info_update(client: AsyncClient):
    reg_resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "profile.user@example.com",
            "password": "Password123",
            "name": "Profile User",
        },
    )
    access_token = reg_resp.json()["access_token"]
    user_id = reg_resp.json()["user"]["id"]

    headers = {"Authorization": f"Bearer {access_token}"}

    # 1. Get initial profile
    profile_resp = await client.get("/api/v1/users/me", headers=headers)
    assert profile_resp.status_code == 200
    assert profile_resp.json()["email"] == "profile.user@example.com"
    assert profile_resp.json()["bank_name"] is None

    # 2. Update profile with bank info for VietQR
    update_payload = {
        "name": "Nguyễn Văn Nam (Updated)",
        "phone": "0912345678",
        "bank_name": "Vietcombank",
        "bank_account_number": "1012345678",
        "bank_account_name": "NGUYEN VAN NAM",
    }
    patch_resp = await client.patch(
        "/api/v1/users/me", json=update_payload, headers=headers
    )
    assert patch_resp.status_code == 200
    updated_data = patch_resp.json()
    assert updated_data["name"] == "Nguyễn Văn Nam (Updated)"
    assert updated_data["phone"] == "0912345678"
    assert updated_data["bank_name"] == "Vietcombank"
    assert updated_data["bank_account_number"] == "1012345678"
    assert updated_data["bank_account_name"] == "NGUYEN VAN NAM"

    # Also test via X-User-Id header (Gateway emulation)
    gateway_resp = await client.get("/api/v1/users/me", headers={"X-User-Id": user_id})
    assert gateway_resp.status_code == 200
    assert gateway_resp.json()["bank_account_number"] == "1012345678"


async def test_search_and_batch_directory(client: AsyncClient):
    # Register 3 users
    u1_resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "alice.wonder@example.com",
            "password": "Password123",
            "name": "Alice Wonder",
        },
    )
    u2_resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "bob.builder@example.com",
            "password": "Password123",
            "name": "Bob Builder",
        },
    )
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "alice.smith@example.com",
            "password": "Password123",
            "name": "Alice Smith",
        },
    )

    u1_id = u1_resp.json()["user"]["id"]
    u2_id = u2_resp.json()["user"]["id"]
    # 1. Search for "Alice" as Bob (should find Alice Wonder and Alice Smith)
    search_resp = await client.get(
        "/api/v1/users/search?query=alice",
        headers={"X-User-Id": u2_id},
    )
    assert search_resp.status_code == 200
    results = search_resp.json()
    assert len(results) == 2
    emails = [r["email"] for r in results]
    assert "alice.wonder@example.com" in emails
    assert "alice.smith@example.com" in emails

    # 2. Search excluding requester (Alice Wonder searching "alice" only sees Alice Smith)
    search_self = await client.get(
        "/api/v1/users/search?query=alice",
        headers={"X-User-Id": u1_id},
    )
    assert search_self.status_code == 200
    assert len(search_self.json()) == 1
    assert search_self.json()[0]["email"] == "alice.smith@example.com"

    # 3. Batch directory endpoint (GET /internal/users/batch?ids=u1&ids=u2)
    batch_resp = await client.get(
        f"/api/v1/internal/users/batch?ids={u1_id}&ids={u2_id}"
    )
    assert batch_resp.status_code == 200
    batch_data = batch_resp.json()
    assert u1_id in batch_data
    assert u2_id in batch_data
    assert batch_data[u1_id]["name"] == "Alice Wonder"
    assert batch_data[u2_id]["name"] == "Bob Builder"

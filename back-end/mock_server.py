"""
Money Judgement - Lightweight FastAPI Mock Server
Run:
    pip install fastapi uvicorn
    uvicorn mock_server:app --port 8000 --reload
Or directly:
    python mock_server.py
"""

import json
import os
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
import uuid

try:
    from fastapi import FastAPI, Header, HTTPException, Query, Response, status
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel
except ImportError:
    print("Vui lòng cài đặt FastAPI và Uvicorn:")
    print("    pip install fastapi uvicorn")
    exit(1)

# Đọc mock-data.json
MOCK_FILE = os.path.join(os.path.dirname(__file__), "mock-data.json")
if not os.path.exists(MOCK_FILE):
    # Fallback to current directory
    MOCK_FILE = "mock-data.json"

with open(MOCK_FILE, "r", encoding="utf-8") as f:
    mock_db: Dict[str, Any] = json.load(f)

app = FastAPI(
    title="Money Judgement Mock Backend API",
    version="1.0.0",
    description="Mock API server phục vụ phát triển Frontend và Backend",
    openapi_url="/api/v1/openapi.json",
    docs_url="/docs"
)

# Kích hoạt CORS cho Next.js dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory mutable state based on seed data
users = list(mock_db["database_seeds"]["users"])
groups = list(mock_db["database_seeds"]["groups"])
group_members = list(mock_db["database_seeds"]["group_members"])
expenses = list(mock_db["database_seeds"]["expenses"])
expense_splits = list(mock_db["database_seeds"]["expense_splits"])
payments = list(mock_db["database_seeds"]["payments"])
notifications = list(mock_db["database_seeds"]["notifications"])
api_res = mock_db["api_responses"]


# ================= AUTH =================

class LoginRequest(BaseModel):
    email: str
    password: str

class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str

class RefreshRequest(BaseModel):
    refresh_token: str

@app.post("/api/v1/auth/login")
def login(payload: LoginRequest, response: Response):
    user = next((u for u in users if u["email"] == payload.email), None)
    if not user:
        # Default fallback to first user
        user = users[0]
    
    token = mock_db["auth"]["jwt_demo_token"]
    refresh_tok = mock_db["auth"]["jwt_refresh_token"]

    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=900,
        path="/"
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_tok,
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=30 * 24 * 3600,
        path="/"
    )

    return {
        "access_token": token,
        "refresh_token": refresh_tok,
        "token_type": "bearer",
        "expires_in": 900,
        "user": {
            "id": user["id"],
            "email": user["email"],
            "name": user["name"],
            "avatar_media_id": user.get("avatar_media_id"),
            "avatar_url": user.get("avatar_url"),
            "is_active": user.get("is_active", True),
            "created_at": user.get("created_at")
        }
    }

@app.post("/api/v1/auth/register", status_code=201)
def register(payload: RegisterRequest):
    new_user = {
        "id": str(uuid.uuid4()),
        "email": payload.email,
        "name": payload.name,
        "avatar_media_id": None,
        "avatar_url": None,
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    users.append(new_user)
    return new_user

@app.post("/api/v1/auth/refresh")
def refresh(payload: RefreshRequest, response: Response):
    res = api_res["auth"]["refresh_success"]
    response.set_cookie(
        key="access_token",
        value=res["access_token"],
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=900,
        path="/"
    )
    return res

@app.post("/api/v1/auth/logout")
def logout(response: Response):
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")
    return api_res["auth"]["logout_success"]


# ================= USERS =================

@app.get("/api/v1/users/me")
def get_me():
    return api_res["users"]["get_me"]

class UserUpdate(BaseModel):
    name: Optional[str] = None
    avatar_media_id: Optional[str] = None

@app.patch("/api/v1/users/me")
def update_me(payload: UserUpdate):
    user = api_res["users"]["get_me"].copy()
    if payload.name:
        user["name"] = payload.name
    if payload.avatar_media_id:
        user["avatar_media_id"] = payload.avatar_media_id
        user["avatar_url"] = "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=150&h=150&fit=crop&crop=face"
    return user

@app.get("/api/v1/users/search")
def search_users(query: str = Query(...)):
    q = query.lower()
    results = [
        {"id": u["id"], "email": u["email"], "name": u["name"], "avatar_url": u.get("avatar_url")}
        for u in users if q in u["email"].lower() or q in u["name"].lower()
    ]
    return results if results else api_res["users"]["search_users"]


# ================= GROUPS =================

@app.get("/api/v1/groups")
def list_groups():
    return api_res["groups"]["list_groups_current_user"] if "list_groups_current_user" in api_res["groups"] else api_res["groups"]["list_groups_for_current_user"]

class GroupCreate(BaseModel):
    name: str
    currency: Optional[str] = "VND"

@app.post("/api/v1/groups", status_code=201)
def create_group(payload: GroupCreate):
    new_group = {
        "id": str(uuid.uuid4()),
        "name": payload.name,
        "currency": payload.currency or "VND",
        "created_by": users[0]["id"],
        "my_role": "OWNER",
        "member_count": 1,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    return new_group

@app.get("/api/v1/groups/{group_id}")
def get_group_detail(group_id: str):
    if group_id == "e2222222-0000-4000-8000-000000000002":
        return api_res["groups"]["group_2_detail"]
    return api_res["groups"]["group_1_detail"]

@app.get("/api/v1/groups/{group_id}/members")
def get_group_members(group_id: str):
    detail = get_group_detail(group_id)
    return detail.get("members", [])

class AddMemberRequest(BaseModel):
    user_id: str

@app.post("/api/v1/groups/{group_id}/members", status_code=201)
def add_group_member(group_id: str, payload: AddMemberRequest):
    user = next((u for u in users if u["id"] == payload.user_id), None)
    return {
        "user_id": payload.user_id,
        "email": user["email"] if user else "newmember@example.com",
        "name": user["name"] if user else "Thành viên mới",
        "avatar_url": user.get("avatar_url") if user else None,
        "role": "MEMBER",
        "status": "ACTIVE",
        "joined_at": datetime.now(timezone.utc).isoformat()
    }

@app.delete("/api/v1/groups/{group_id}/members/{user_id}", status_code=204)
def remove_group_member(group_id: str, user_id: str):
    return None


# ================= EXPENSES =================

@app.get("/api/v1/groups/{group_id}/expenses")
def list_expenses(group_id: str, page: int = 1, page_size: int = 20):
    return api_res["expenses"]["list_expenses_group_1"]

class SplitItem(BaseModel):
    user_id: str
    amount_owed: Optional[int] = None

class ExpenseCreate(BaseModel):
    description: str
    amount: int
    paid_by: str
    split_type: str
    splits: List[SplitItem]
    bill_media_id: Optional[str] = None

@app.post("/api/v1/groups/{group_id}/expenses", status_code=201)
def create_expense(group_id: str, payload: ExpenseCreate):
    new_id = str(uuid.uuid4())
    payer = next((u for u in users if u["id"] == payload.paid_by), users[0])
    return {
        "id": new_id,
        "group_id": group_id,
        "paid_by": payload.paid_by,
        "paid_by_name": payer["name"],
        "amount": payload.amount,
        "currency": "VND",
        "description": payload.description,
        "split_type": payload.split_type,
        "version": 1,
        "has_bill": bool(payload.bill_media_id),
        "created_at": datetime.now(timezone.utc).isoformat()
    }

@app.get("/api/v1/expenses/{expense_id}")
def get_expense_detail(expense_id: str):
    if "4" in expense_id:
        return api_res["expenses"]["expense_detail_exact"]
    return api_res["expenses"]["expense_detail_equal"]

@app.patch("/api/v1/expenses/{expense_id}")
def update_expense(expense_id: str, payload: Dict[str, Any]):
    detail = get_expense_detail(expense_id).copy()
    if "description" in payload:
        detail["description"] = payload["description"]
    if "amount" in payload:
        detail["amount"] = payload["amount"]
    detail["version"] = detail.get("version", 1) + 1
    detail["updated_at"] = datetime.now(timezone.utc).isoformat()
    return detail

@app.delete("/api/v1/expenses/{expense_id}", status_code=204)
def delete_expense(expense_id: str):
    return None


# ================= LEDGER & SETTLEMENT =================

@app.get("/api/v1/groups/{group_id}/balances")
def get_group_balances(group_id: str):
    if group_id == "e2222222-0000-4000-8000-000000000002":
        return api_res["balances"]["group_2_balances"]
    if group_id == "e3333333-0000-4000-8000-000000000003":
        return api_res["balances"]["group_3_balances"]
    return api_res["balances"]["group_1_balances"]

@app.get("/api/v1/groups/{group_id}/settlements")
def get_group_settlements(group_id: str):
    if group_id == "e2222222-0000-4000-8000-000000000002":
        return api_res["settlements"]["group_2_settlements"]
    if group_id == "e3333333-0000-4000-8000-000000000003":
        return api_res["settlements"]["group_3_settlements"]
    return api_res["settlements"]["group_1_settlements"]

@app.get("/api/v1/groups/{group_id}/payments")
def list_payments(group_id: str, page: int = 1, page_size: int = 20):
    return api_res["payments"]["list_payments_group_1"]

class PaymentCreate(BaseModel):
    from_user: str
    to_user: str
    amount: int

@app.post("/api/v1/groups/{group_id}/payments", status_code=201)
def record_payment(group_id: str, payload: PaymentCreate):
    from_u = next((u for u in users if u["id"] == payload.from_user), None)
    to_u = next((u for u in users if u["id"] == payload.to_user), None)
    return {
        "id": str(uuid.uuid4()),
        "group_id": group_id,
        "from_user": payload.from_user,
        "from_user_name": from_u["name"] if from_u else "Người gửi",
        "to_user": payload.to_user,
        "to_user_name": to_u["name"] if to_u else "Người nhận",
        "amount": payload.amount,
        "currency": "VND",
        "created_at": datetime.now(timezone.utc).isoformat()
    }


# ================= NOTIFICATIONS =================

@app.get("/api/v1/notifications")
def list_notifications(page: int = 1, page_size: int = 20):
    return api_res["notifications"]["list_notifications"]

@app.get("/api/v1/notifications/unread-count")
def get_unread_count():
    return api_res["notifications"]["unread_count"]

@app.patch("/api/v1/notifications/{notification_id}/read")
def mark_notification_read(notification_id: str):
    return api_res["notifications"]["mark_read_response"]

@app.patch("/api/v1/notifications/read-all")
def mark_all_notifications_read():
    return api_res["notifications"]["mark_all_read_response"]


# ================= MEDIA =================

class MediaUploadRequest(BaseModel):
    ref_type: str
    mime_type: str
    size_bytes: Optional[int] = None

@app.post("/api/v1/media/upload-url")
def request_upload_url(payload: MediaUploadRequest):
    return api_res["media"]["upload_url_response"]

@app.post("/api/v1/media/{media_id}/confirm")
def confirm_media(media_id: str):
    return {"media_id": media_id, "status": "READY"}


if __name__ == "__main__":
    import uvicorn
    print("🚀 Đang khởi động Money Judgement Mock Server tại http://localhost:8000/api/v1...")
    print("📖 Swagger Docs: http://localhost:8000/docs")
    print("👤 Đăng nhập mặc định: nam.nguyen@example.com / Password123!")
    uvicorn.run(app, host="0.0.0.0", port=8000)

# Hướng Dẫn Sử Dụng Mock Data & Mock Server Cho Backend & Frontend

Tài liệu này hướng dẫn cách sử dụng tệp [`mock-data.json`](./mock-data.json) để:
1. Seed dữ liệu mẫu vào Database (PostgreSQL / SQLite / MongoDB).
2. Chạy Mock API Server bằng FastAPI (hoặc Prism) để phục vụ phát triển độc lập cho Frontend.

---

## 1. Vị trí tệp Mock Data

- Frontend source: [`front-end/src/mocks/mock-data.json`](file:///home/trgphun/projects/personal/money-jugement/front-end/src/mocks/mock-data.json)
- API Contracts docs: [`front-end/plan/docs/api-contracts/mock-data.json`](file:///home/trgphun/projects/personal/money-jugement/front-end/plan/docs/api-contracts/mock-data.json)
- Backend directory: [`back-end/mock-data.json`](file:///home/trgphun/projects/personal/money-jugement/back-end/mock-data.json)

---

## 2. Cấu trúc của `mock-data.json`

Tệp JSON được thiết kế thành 2 phân vùng dữ liệu để tối ưu cho cả 2 nhu cầu:

### Phân vùng 1: `database_seeds` (Dành cho Seeding Database / ORM)
Chứa các mảng đối tượng tương ứng với các bảng trong cơ sở dữ liệu quan hệ:
- **`users`** (4 tài khoản người dùng thực tế với avatar, email, mật khẩu băm mẫu)
- **`groups`** (3 nhóm đại diện: Du lịch, Nhà trọ, Cà phê văn phòng)
- **`group_members`** (Phân quyền `OWNER` / `MEMBER`, trạng thái `ACTIVE`)
- **`expenses`** (Các khoản chi VND với `split_type: "EQUAL"` và `"EXACT"`)
- **`expense_splits`** (Chi tiết số tiền từng người gánh, tổng luôn khớp 100% với `expense.amount`)
- **`payments`** (Lịch sử thanh toán nợ giữa các thành viên)
- **`notifications`** (Thông báo in-app: thêm chi tiêu, nhận tiền, xác nhận thanh toán, mời vào nhóm)
- **`media`** (Metadata ảnh hóa đơn MinIO và ảnh đại diện)

### Phân vùng 2: `api_responses` (Dành cho Mock Controller / FastAPI Handlers)
Chứa sẵn các payload response JSON chuẩn khớp 100% với [`openapi.yaml`](./openapi.yaml) và TypeScript [`types.ts`](./types.ts):
- `auth`: `login_success`, `register_success`, `refresh_success`, `logout_success`
- `users`: `get_me`, `update_me_success`, `search_users`
- `groups`: `list_groups_for_current_user`, `group_1_detail`, `group_2_detail`, `create_group_success`
- `expenses`: `list_expenses_group_1`, `expense_detail_equal`, `expense_detail_exact`
- `balances`: `group_1_balances`, `group_2_balances`, `group_3_balances` (tất cả net balance đều có tổng = 0)
- `settlements`: `group_1_settlements`, `group_2_settlements`, `group_3_settlements`
- `payments`: `list_payments_group_1`, `create_payment_success`
- `notifications`: `list_notifications`, `unread_count`, `mark_read_response`, `mark_all_read_response`
- `media`: `upload_url_response`, `confirm_response`
- `errors`: Các mã lỗi chuẩn (`UNAUTHORIZED`, `FORBIDDEN`, `NOT_FOUND`, `INVALID_SPLIT_SUM`, `CANNOT_LEAVE_UNSETTLED_GROUP`)

---

## 3. Tài khoản kiểm thử mặc định (Demo Credentials)

| Họ và Tên | Email | Mật khẩu | Vai trò mẫu |
| :--- | :--- | :--- | :--- |
| **Nguyễn Văn Nam** | `nam.nguyen@example.com` | `Password123!` | Owner Nhóm 1, Member Nhóm 2 (Mặc định đăng nhập) |
| **Trần Thị Lan** | `lan.tran@example.com` | `Password123!` | Member Nhóm 1, Owner Nhóm 2 |
| **Lê Hoàng Long** | `long.le@example.com` | `Password123!` | Member Nhóm 1, Member Nhóm 2 |
| **Phạm Minh Thư** | `thu.pham@example.com` | `Password123!` | Member Nhóm 1 (Người nợ tiền) |

---

## 4. Kịch bản nghiệp vụ có sẵn trong Mock Data

### Nhóm 1: "Chuyến Du Lịch Đà Lạt 🌸" (`id: e1111111-0000-4000-8000-000000000001`)
- **Tổng chi tiêu**: 4.400.000 ₫ (4 hóa đơn: Vé xe limousine, Homestay, Lẩu gà, Cà phê).
- **Trạng thái nợ (Balances)**:
  - Lan: được nhận lại `+615.000 ₫` (`OWED`)
  - Nam: được nhận lại `+410.000 ₫` (`OWED`)
  - Long: nợ `-245.000 ₫` (`OWES`)
  - Thư: nợ `-780.000 ₫` (`OWES`)
  - *Tổng nợ ròng:* `+615 + +410 - 245 - 780 = 0 ₫`.
- **Gợi ý tất toán rút gọn (Settlements)**:
  1. Thư $\rightarrow$ Lan: 615.000 ₫
  2. Thư $\rightarrow$ Nam: 165.000 ₫
  3. Long $\rightarrow$ Nam: 245.000 ₫

### Nhóm 2: "Tiền Trọ & Sinh Hoạt Tháng 10 🏠" (`id: e2222222-0000-4000-8000-000000000002`)
- **Tổng chi tiêu**: 5.190.000 ₫ (Tiền phòng, điện nước, nước uống).
- **Trạng thái nợ**:
  - Lan: được nhận `+2.770.000 ₫`
  - Nam: nợ `-1.130.000 ₫`
  - Long: nợ `-1.640.000 ₫`
- **Gợi ý tất toán**:
  1. Nam $\rightarrow$ Lan: 1.130.000 ₫
  2. Long $\rightarrow$ Lan: 1.640.000 ₫

### Nhóm 3: "Cà Phê & Ăn Trưa Tech Team ☕" (`id: e3333333-0000-4000-8000-000000000003`)
- **Đã tất toán toàn bộ** (`is_settled: true`, balances = 0).

---

## 5. Cách chạy Mock Server

### Cách A: Chạy FastAPI Mock Server tích hợp sẵn (Khuyên dùng)
Tệp [`back-end/mock_server.py`](file:///home/trgphun/projects/personal/money-jugement/back-end/mock_server.py) đã được cấu hình sẵn CORS và các route `/api/v1/*`:

```bash
cd back-end
pip install fastapi uvicorn
python mock_server.py
```
- API Base URL: `http://localhost:8000/api/v1`
- Swagger UI tài liệu tương tác: `http://localhost:8000/docs`

### Cách B: Chạy qua Stoplight Prism CLI
```bash
npx @stoplight/prism-cli mock front-end/plan/docs/api-contracts/openapi.yaml -p 8000
```

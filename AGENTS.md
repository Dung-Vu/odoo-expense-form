# Odoo Expense Form — Developer & Agent Guide

> **Context:** Hệ thống web form gửi chi phí vào **Odoo 19 SaaS** qua JSON-RPC thay thế luồng gửi qua email `expense@...`. Giải quyết triệt để lỗi phân loại nhầm công ty trong mô hình multi-company (Bonario & Ordinaire) bằng việc bắt buộc người dùng chọn công ty cụ thể trên form.

---

## 1. Kiến trúc & Mô hình "Broker"

### Kiến trúc tổng thể
```
Browser (HTMX)  ──[HTTP]──>  Flask Proxy (Docker :5000 / Host :5055)  ──[JSON-RPC]──>  Odoo 19 SaaS
```
- **Không database riêng:** Toàn bộ dữ liệu nằm trực tiếp trên Odoo.
- **Không frontend build-step:** Giao diện rendered từ Jinja2 + HTMX 2.x + Vanilla CSS.
- **Proxy server an toàn:** Ẩn `ODOO_API_KEY` ở backend, mã hóa file base64 cho `ir.attachment`, vượt qua giới hạn CORS của Odoo SaaS.

### Broker Pattern (Cực kỳ quan trọng)
Hệ thống sử dụng **API key của 1 user admin duy nhất** (Broker) để tạo và nộp chi phí thay cho các nhân viên khác.
- `hr.expense.create()` cho phép truyền `employee_id` và `company_id` tùy ý.
- `hr.expense.action_submit()` **bắt buộc** user gọi API phải thuộc nhóm `hr_expense.group_hr_expense_manager` (Quản trị chi phí) nếu nộp thay cho người khác.
- `create_uid` trên Odoo sẽ là user Broker (tương tự như luồng email alias của Odoo bản chất cũng mang `create_uid = Superuser`), trong khi quyền sở hữu nghiệp vụ và luồng duyệt gắn đúng với `employee_id`.

---

## 2. Quy tắc nghiệp vụ & Luồng xử lý

### 1. Caching & Danh sách Dropdown (GET `/`)
Dữ liệu dropdown được cache trong bộ nhớ **5 phút** (`CACHE_TTL = 300`):
- **Công ty:** Lọc theo `COMPANY_IDS`.
- **Nhân viên:** Lấy nhân viên thuộc các công ty trên, sau đó lọc trong Python theo:
  - Tên tiếng Việt: Khớp từ cuối cùng (`_last_word`) với `EMPLOYEE_NAME_KEYWORDS` (ví dụ: "Phước", "Công", "Thành").
  - Hoặc khớp ID cụ thể trong `EMPLOYEE_IDS`.
- **Hạng mục (Danh mục chi phí):** Lọc sản phẩm `product.product` có `can_be_expensed=True` theo danh sách ID trong `CATEGORY_IDS`.
- **Tiền tệ:** Lọc theo `CURRENCY_CODES`. Nếu chỉ có 1 loại tiền (ví dụ: `VND`), form tự ẩn dropdown và gửi dưới dạng input ẩn.
- **Nhà cung cấp:** Lọc `res.partner` có `supplier_rank > 0` thuộc công ty đã chọn.

### 2. Xử lý gửi chi phí (POST `/submit`)
- **Hình thức chi trả (`payment_mode`):**
  - `own_account`: Nhân viên chi trả (mặc định).
  - `company_account`: Công ty chi trả -> **Bắt buộc** phải chọn `vendor_id`.
- **Đính kèm chứng từ (`attachment_ids`):**
  - Nhận nhiều file từ input (`receipt` hoặc `receipts`), dung lượng tối đa 16MB/file.
  - Mã hóa base64 và gán vào `attachment_ids` theo cú pháp Odoo Command `(0, 0, {...})`.
- **Phân luồng duyệt:**
  - Tạo record chi phí ở trạng thái `draft`.
  - **Chỉ tự động gọi `action_submit()`** nếu `employee_id` nằm trong `AUTO_SUBMIT_EMPLOYEE_IDS` (ví dụ: anh Bảo). Các nhân viên còn lại sẽ giữ ở trạng thái `draft` trên Odoo để rà soát trước.

---

## 3. Cấu trúc thư mục

```text
odoo-expense-form/
├── AGENTS.md                  ← Tài liệu kỹ thuật chi tiết cho Agent & Developer
├── README.md                  ← Tài liệu hướng dẫn sử dụng & vận hành
├── Dockerfile                 ← python:3.12-slim + gunicorn (chạy port 5000)
├── docker-compose.yml         ← Mapping port 5055:5000, network: bonario-shared-tunnel
├── requirements.txt           ← flask, httpx, gunicorn, python-dotenv
├── .env.example               ← Template cấu hình
├── .env                       ← File môi trường thực tế (chứa API Key, gitignored)
├── .gitignore
├── app/
│   ├── __init__.py
│   ├── main.py                ← Flask endpoints, validation, cache, submit logic
│   ├── odoo_client.py         ← Client wrapper gọi Odoo JSON-RPC
│   ├── templates/
│   │   ├── base.html          ← Layout chính, CDN HTMX
│   │   ├── index.html         ← Form nhập liệu (dynamic filter JS, drag-drop upload)
│   │   ├── _success.html      ← HTMX partial khi gửi thành công
│   │   └── _error.html        ← HTMX partial khi có lỗi
│   └── static/
│       └── style.css          ← Style CSS toàn bộ form
└── tests/
    ├── __init__.py
    ├── test_connectivity.py   ← Kiểm tra kết nối & quyền nhóm của user broker
    ├── test_create.py         ← Tạo & submit thử 1 chi phí mẫu
    └── test_attachment.py     ← Tạo chi phí mẫu đính kèm file ảnh base64
```

---

## 4. Biến môi trường (`.env`)

| Biến | Bắt buộc | Ví dụ | Ý nghĩa |
|---|---|---|---|
| `ODOO_URL` | Có | `https://testing2007.odoo.com` | URL Odoo (không có dấu `/` ở cuối) |
| `ODOO_DB` | Có | `testing2007` | Database name của Odoo |
| `ODOO_UID` | Có | `208` | User ID của tài khoản broker |
| `ODOO_API_KEY` | Có | `xxxxxxxxxxxx` | API key được tạo từ My Profile của broker |
| `COMPANY_IDS` | Có | `1,11` | ID các công ty hiển thị trên form |
| `EMPLOYEE_NAME_KEYWORDS` | Có | `Phước,Thành,Công,Biên,Chinh` | Từ khóa tên nhân viên hiển thị (khớp tên gọi) |
| `EMPLOYEE_IDS` | Không | `138,396` | ID nhân viên cụ thể bổ sung ngoài từ khóa |
| `CATEGORY_IDS` | Có | `26807,26758,157600...` | ID các `product.product` dùng làm danh mục |
| `CURRENCY_CODES` | Không | `VND` | Mã tiền tệ cho phép (mặc định VND) |
| `AUTO_SUBMIT_EMPLOYEE_IDS` | Không | `138,396` | Nhân viên được tự động submit sau khi tạo |
| `PUBLIC_ODOO_DOMAIN` | Không | `bonario-vietnam.odoo.com` | Tên miền Odoo dùng tạo link xem trực tiếp |

---

## 5. Những điểm cần đặc biệt chú ý (Gotchas)

1. **Quyền của Broker:** Nếu đổi user broker trong `.env`, bắt buộc user đó phải thuộc nhóm **Expense / Administrator** (`group_hr_expense_manager`). Nếu không, hàm `action_submit` sẽ văng lỗi `UserError`.
2. **Cú pháp đính kèm file:** Trường đính kèm trên `hr.expense` là số nhiều: `attachment_ids`. Phải truyền mảng commands: `[(0, 0, {'name': ..., 'datas': ..., 'mimetype': ..., 'res_model': 'hr.expense'})]`.
3. **Cơ chế cache dropdown:** Khi sửa biến môi trường whitelist (`EMPLOYEE_NAME_KEYWORDS`, `CATEGORY_IDS`...) cần khởi động lại container hoặc chờ 5 phút để cache hết hạn.
4. **An toàn kiểm thử:** Tất cả file trong `tests/` chỉ chạy được khi URL trỏ vào database test (có chữ `testing`). Tuyệt đối không xóa cơ chế an toàn này để tránh tạo rác trên database production.
5. **Cổng dịch vụ:** Dockerfile chạy port `5000`, `docker-compose.yml` map ra ngoài host ở cổng `5055`.

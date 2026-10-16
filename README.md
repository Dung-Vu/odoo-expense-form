# Odoo Expense Submission Form

Web form tinh gọn giúp nhân viên gửi chi phí trực tiếp vào **Odoo 19 SaaS** qua JSON-RPC, giải quyết triệt để vấn đề phân loại nhầm công ty (multi-company) so với cách gửi email truyền thống.

---

## Tính năng chính

- **Chọn đúng công ty:** Phân loại chính xác chứng từ cho từng pháp nhân (Bonario / Ordinaire).
- **Lọc nhân viên theo công ty:** Danh sách nhân viên và nhà cung cấp tự động cập nhật tương ứng theo công ty đã chọn.
- **Hạng mục & Tiền tệ:** Chọn danh mục chi phí (đồng bộ từ `product.product`) và số tiền chi tiêu.
- **Hình thức chi trả linh hoạt:**
  - *Nhân viên chi trả:* Công ty sẽ hoàn tiền lại cho nhân viên.
  - *Công ty chi trả:* Yêu cầu chọn Nhà cung cấp tương ứng.
- **Đính kèm nhiều chứng từ:** Kéo thả tải lên cùng lúc nhiều file ảnh hoặc PDF (tối đa 16MB/file).
- **Phân luồng duyệt thông minh:** Tự động gửi duyệt (`Submitted`) cho nhân sự được cấu hình hoặc lưu bản nháp (`Draft`).
- **Liên kết trực tiếp:** Cung cấp link mở thẳng hồ sơ chi phí trên Odoo sau khi gửi thành công.

---

## Công nghệ sử dụng

- **Backend:** Python 3.12, Flask 3, httpx
- **Frontend:** Server-rendered Jinja2, HTMX 2.x (không cần build-step), Vanilla CSS
- **Server & Container:** Gunicorn, Docker & Docker Compose
- **Tích hợp:** Odoo 19 SaaS JSON-RPC API

---

## Hướng dẫn cài đặt & Khởi chạy

### 1. Cấu hình file môi trường
Tạo file `.env` từ `.env.example`:
```bash
cp .env.example .env
```
Điền các thông tin Odoo:
```env
ODOO_URL=https://your-tenant.odoo.com
ODOO_DB=your-db-name
ODOO_UID=your_admin_uid
ODOO_API_KEY=your_odoo_api_key
```

### 2. Khởi chạy bằng Docker
```bash
docker compose up -d --build
```

### 3. Truy cập ứng dụng
- **Cục bộ (Local):** `http://localhost:5055`
- **Tên miền công khai:** `https://chiphi.bonstu.site`

---

## Kiểm thử (Testing)

Các script kiểm thử nằm trong thư mục `tests/`:
```bash
python tests/test_connectivity.py   # Kiểm tra kết nối & quyền của tài khoản broker
python tests/test_create.py         # Kiểm tra tạo chi phí nháp và submit
python tests/test_attachment.py     # Kiểm tra đính kèm file chứng từ
```

> **Lưu ý bảo vệ dữ liệu:** Tất cả script trong `tests/` đều tích hợp cơ chế bảo vệ tự động: chỉ cho phép chạy khi `ODOO_URL` là server test (có chứa từ khóa `testing`). Script sẽ tự động ngắt nếu trỏ vào server production.

---

## Các lệnh bảo trì thường dùng

- **Xem log hệ thống:**
  ```bash
  docker compose logs -f web
  ```
- **Khởi động lại service:**
  ```bash
  docker compose restart web
  ```
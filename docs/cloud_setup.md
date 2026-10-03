# Hướng dẫn Thiết lập Chạy Cloud 100% (Đảm bảo độ trễ 30 phút - 1 giờ)

Tài liệu này hướng dẫn cách vận hành hệ thống Facebook Post Notifier hoàn toàn trên nền tảng đám mây (Cloud 24/7) mà **không cần mở máy tính cá nhân**, đảm bảo **không bao giờ bỏ sót bài viết** và **độ trễ thông báo luôn dưới 30 - 60 phút**.

---

## 1. Cơ chế vận hành Cloud 2 lớp (Dual-Trigger)

GitHub Actions miễn phí có một hạn chế: lịch chạy định kỳ (`schedule: cron`) dùng chung hàng đợi (shared queue) với hàng triệu repository khác, nên vào các mốc giờ cao điểm (:00, :15, :30, :45) có thể bị nghẽn (delay từ 1–3 tiếng).

Để giải quyết triệt để, hệ thống sử dụng kiến trúc kết hợp:
1. **Kích hoạt tức thì (Primary)**: Sử dụng dịch vụ webhook miễn phí ([cron-job.org](https://cron-job.org)) gửi lệnh `repository_dispatch` định kỳ 30 phút/lần. GitHub ưu tiên lệnh này ở mức cao nhất, runner khởi động ngay lập tức (<15 giây).
2. **Kích hoạt dự phòng (Backup)**: GitHub Actions Scheduled Cron chạy ở phút lệch (`11,41 * * * *`) để tránh giờ cao điểm.
3. **Chống tự động tắt (Keepalive)**: GitHub mặc định tắt các workflow cron nếu repo không có commit sau 60 ngày. Workflow đã được tích hợp `keepalive-workflow` để duy trì hoạt động vĩnh viễn.

---

## 2. Hướng dẫn thiết lập Webhook kích hoạt 30 phút/lần (cron-job.org)

Thiết lập này hoàn toàn miễn phí, không yêu cầu thẻ tín dụng và chỉ mất khoảng 3 phút:

### Bước 1: Tạo GitHub Personal Access Token (PAT)
1. Đăng nhập GitHub, vào: **Settings** (ở góc trên cùng bên phải) > **Developer settings** > **Personal access tokens** > **Tokens (classic)**.
   *(Hoặc truy cập trực tiếp: https://github.com/settings/tokens)*
2. Bấm **Generate new token** > chọn **Generate new token (classic)**.
3. Điền thông tin:
   - **Note**: `Cron-job Trigger for Noti_App`
   - **Expiration**: Chọn `No expiration` (hoặc thời hạn bạn muốn).
   - **Select scopes**: Tích chọn ô `repo` (đầy đủ quyền quản lý repository và triggers).
4. Kéo xuống dưới cùng và bấm **Generate token**.
5. **Copy mã token** (dạng `ghp_xxxxxxxxxxxx...`). *Lưu ý: GitHub chỉ hiện mã này một lần duy nhất.*

---

### Bước 2: Đăng ký & Tạo Job trên cron-job.org
1. Truy cập https://cron-job.org và đăng ký tài khoản miễn phí (nếu chưa có).
2. Sau khi đăng nhập, chọn tab **Cronjobs** > bấm nút **CREATE CRONJOB**.
3. Điền thông tin cấu hình như sau:

| Mục cấu hình | Giá trị |
| :--- | :--- |
| **Title** | `Noti_App Facebook Trigger` |
| **URL** | `https://api.github.com/repos/nguynie/Noti_App/dispatches` |
| **Execution schedule** | Chọn **Every 30 minutes** (hoặc Custom: `*/30 * * * *`) |
| **Request method** | Chọn `POST` |

4. Bấm vào mục **Advanced** (hoặc **Request Headers / Request Body**):
   - **Headers**: Thêm 3 header sau:
     - `Authorization`: `Bearer ghp_xxxxxxxxxxxxxxxxxxxx` *(thay ghp_... bằng token bạn vừa tạo ở Bước 1)*
     - `Accept`: `application/vnd.github+json`
     - `User-Agent`: `cron-job-org`
   - **Request Body**:
     ```json
     {"event_type": "check-pages-webhook"}
     ```

5. Bấm nút **CREATE** để lưu.

---

### Bước 3: Kiểm tra kết quả
1. Trong danh sách Cronjob trên cron-job.org, bấm vào nút **Test run** (biểu tượng Play hoặc nút Run).
2. Kết quả trả về mã **HTTP 204 No Content** là thành công.
3. Chuyển sang GitHub tab **Actions** của repository `nguynie/Noti_App`:
   Bạn sẽ thấy một workflow **Facebook Page Notifier** được kích hoạt ngay lập tức qua `repository_dispatch`.

---

## 3. Hệ thống Cảnh báo Quản trị qua Telegram (Admin Alerts)

Hệ thống đã được tích hợp cơ chế tự chẩn đoán phiên đăng nhập Facebook:
- Nếu Facebook yêu cầu xác minh bảo mật (Checkpoint) hoặc Cookies đăng nhập hết hạn, bot Telegram sẽ tự động gửi một thông báo cảnh báo:
  ```text
  ⚠️ [HCMUS Notifier - Cảnh báo Hệ thống]

  Phát hiện lỗi phiên đăng nhập Facebook (Cookies đã hết hạn hoặc bị yêu cầu xác thực Checkpoint).
  Chi tiết: Redirected to auth/checkpoint...

  👉 Vui lòng cập nhật FB_COOKIES trong GitHub Secrets (Settings > Secrets and variables > Actions) để tiếp tục nhận thông báo tự động!
  ```
- Cảnh báo này có cơ chế giới hạn tần suất (tối đa 1 lần / 24 giờ) để không gây phiền hà.
- Khi nhận được cảnh báo này, bạn chỉ cần xuất lại chuỗi cookies mới từ trình duyệt và dán vào secret `FB_COOKIES` trên GitHub repo.

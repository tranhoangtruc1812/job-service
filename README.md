# Job Service (Flask + Cron + Worker)

Service gồm 2 phần:
- **Flask API**: health check + trigger thủ công.
- **Worker**: script chạy 1 lần để gọi API nguồn và gửi Telegram.

Lịch chạy mỗi 20 phút được giao cho **cron**.

## 1) Cài đặt

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## 2) Cấu hình

Sửa file `.env`:
- `SOURCE_API_URL`: endpoint cần lấy dữ liệu.
- `TELEGRAM_BOT_TOKEN`: token bot Telegram.
- `TELEGRAM_CHAT_ID`: chat id nhận tin nhắn.

### Hỗ trợ tự refresh access token khi hết hạn

Worker sẽ:
1. Gọi source API với `SOURCE_API_ACCESS_TOKEN` (nếu có).
2. Nếu nhận `401 Unauthorized` và có `TOKEN_URL`, worker sẽ gọi token endpoint để lấy token mới.
3. Retry source API đúng 1 lần với token mới.

Các biến liên quan:
- `SOURCE_API_ACCESS_TOKEN`
- `TOKEN_URL`
- `TOKEN_CLIENT_ID`
- `TOKEN_CLIENT_SECRET`
- `TOKEN_SCOPE` (optional)
- `TOKEN_FIELD_NAME` (mặc định `access_token`)

## 3) Chạy Flask service

```bash
set -a
source .env
set +a
python app.py
```

## 4) Chạy worker thủ công

```bash
set -a
source .env
set +a
python worker.py
```

## 5) Cấu hình cron (mỗi 20 phút)

Mở crontab:

```bash
crontab -e
```

Thêm dòng sau (đổi đúng đường dẫn máy bạn):

```cron
*/20 * * * * cd /workspace/job-service && /usr/bin/env bash -lc 'set -a; source .env; set +a; python worker.py >> worker.log 2>&1'
```

## 6) API local

- `GET /` kiểm tra trạng thái service.
- `POST /run-now` chạy job ngay lập tức (không cần đợi cron).

## 7) CI/CD (GitHub Actions)

Project đã được thêm 2 luồng tự động:

- **CI** (`.github/workflows/ci.yml`)
  - Chạy khi `push`/`pull_request` lên `main` hoặc `master`.
  - Cài dependencies từ `requirements.txt`.
  - Kiểm tra syntax với `python -m compileall`.
  - Smoke test import `app.py` và `worker.py`.

- **CD** (`.github/workflows/cd.yml`)
  - Chạy khi `push` lên `main`/`master`, khi tạo tag `v*`, hoặc chạy tay (`workflow_dispatch`).
  - Build Docker image từ `Dockerfile`.
  - Push image lên **GHCR** với các tag theo branch/tag/commit SHA.
  - Có bước tùy chọn gọi webhook deploy nếu cấu hình `DEPLOY_WEBHOOK_URL`.

### Secrets khuyến nghị

Trong GitHub repo settings → **Secrets and variables** → **Actions**, thêm:

- `DEPLOY_WEBHOOK_URL` (optional): URL để trigger deploy trên server/platform của bạn.

> Ghi chú: Push lên GHCR dùng sẵn `GITHUB_TOKEN` nên không cần tạo PAT cho luồng mặc định.

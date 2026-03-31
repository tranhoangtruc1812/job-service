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

## 8) Deploy source này lên VPS (Docker + GitHub Actions)

Dưới đây là cách deploy thực tế để service chạy tự động sau mỗi lần merge vào `main`.

### Bước A: Chuẩn bị VPS

Cài Docker + Docker Compose plugin (Ubuntu ví dụ):

```bash
sudo apt update
sudo apt install -y docker.io docker-compose-plugin
sudo usermod -aG docker $USER
newgrp docker
```

Tạo thư mục deploy:

```bash
sudo mkdir -p /opt/job-service
sudo chown -R $USER:$USER /opt/job-service
cd /opt/job-service
```

Tạo file `.env` với đúng biến môi trường của app (SOURCE_API_URL, TELEGRAM_BOT_TOKEN, ...).

### Bước B: Cấu hình GitHub Secrets

Vào **Settings → Secrets and variables → Actions** thêm:

- `VPS_HOST`: IP/Domain server
- `VPS_USER`: user SSH (vd: `ubuntu`)
- `VPS_SSH_KEY`: private key SSH (dạng PEM)
- `VPS_PORT`: port SSH (optional, mặc định 22)
- `GHCR_PAT`: GitHub token có quyền `read:packages` để pull image private từ GHCR

### Bước C: Luồng CI/CD/Deploy

1. `CI` chạy test/check khi push hoặc pull request.
2. `CD` build + push image lên `ghcr.io/<owner>/<repo>:main`.
3. `Deploy to VPS` (workflow mới) tự SSH vào VPS và chạy:
   - `docker compose pull`
   - `docker compose up -d`

### Bước D: Deploy thủ công lần đầu trên VPS

Nếu muốn chạy tay trước khi dùng workflow auto, trên VPS:

```bash
docker login ghcr.io -u <github-username>
docker compose -f deploy-compose.yml pull
docker compose -f deploy-compose.yml up -d
```

### Verify sau deploy

```bash
docker ps
curl http://<VPS_IP>:5000/
```

Nếu trả về JSON trạng thái service là deploy thành công.

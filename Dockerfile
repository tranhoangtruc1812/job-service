# Sử dụng image Python gọn nhẹ
FROM python:3.11-slim

# Đặt múi giờ mặc định sang Việt Nam (rất quan trọng cho việc hẹn giờ cron)
ENV TZ="Asia/Ho_Chi_Minh"
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

WORKDIR /app

# Ngăn Python sinh file cache .pyc và hiển thị log ngay lập tức
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Copy & cài đặt thư viện
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy toàn bộ code vào bên trong container
COPY . .

# Port được sử dụng (có thể cấu hình lại qua env)
EXPOSE 5000

# Khởi chạy dịch vụ (Chỉ dùng 1 process để tránh APScheduler chạy lặp)
CMD ["python", "app.py"]

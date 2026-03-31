import os
from dotenv import load_dotenv

load_dotenv()

from flask import Flask, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
import atexit

from worker import run_job

app = Flask(__name__)

RUN_TIME = os.getenv("RUN_TIME", "20")
# Khởi tạo Background Scheduler để chạy ngầm cùng Flask
scheduler = BackgroundScheduler()
# Cấu hình job chạy mỗi 20 phút
scheduler.add_job(func=run_job, trigger="interval", minutes=int(RUN_TIME))
scheduler.start()

# Tắt scheduler an toàn khi tắt app
atexit.register(lambda: scheduler.shutdown())

@app.route("/")
def index():
    return jsonify(
        {
            "service": "job-service",
            "mode": "integrated (flask + apscheduler)",
            "status": "running",
            "cron_schedule": f"Every {RUN_TIME} minutes",
        }
    )


@app.route("/run-now", methods=["POST"])
def run_now():
    run_job()
    return jsonify({"status": "triggered"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")))

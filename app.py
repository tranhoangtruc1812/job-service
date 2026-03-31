import os

from flask import Flask, jsonify

from worker import run_job

app = Flask(__name__)


@app.route("/")
def index():
    return jsonify(
        {
            "service": "job-service",
            "mode": "cron + worker",
            "status": "running",
            "cron_schedule": "*/20 * * * *",
        }
    )


@app.route("/run-now", methods=["POST"])
def run_now():
    run_job()
    return jsonify({"status": "triggered"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")))

from flask import Flask, request, jsonify, send_file
import os
from datetime import datetime, timedelta
from urllib.parse import quote
from script import messedge_tts
import edge_tts
import asyncio
import pygame
import io


app = Flask(__name__)
SERVER_HOST = "10.250.111.110"  # 实际 IP
PORT = 5000

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


LOG_FILE_PATH = os.path.join(BASE_DIR, "abnormal_log.txt")
IMAGE_FOLDER = os.path.join(BASE_DIR, "captured_images")
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png"}



@app.route("/submit_text", methods=["POST"])
def receive_text():
    data = request.get_json()
    user_text = data.get("text", "")
    print(f"[提醒文本] {user_text}")
    asyncio.run(messedge_tts.text_to_speech_play(user_text, rate="+0%"))
    return jsonify({"status": "success", "message": "文本已收到"}), 200


@app.route("/get_recent_abnormal", methods=["GET"])
def get_recent_abnormal():
    if not os.path.exists(LOG_FILE_PATH):
        return jsonify({"status": "error", "message": "暂无异常记录"}), 404

    three_days_ago = datetime.now() - timedelta(days=3)
    recent_logs = []

    with open(LOG_FILE_PATH, "r") as f:
        for line in f:
            try:
                date_str, message = line.strip().split(" | ", 1)
                log_time = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
                if log_time >= three_days_ago:
                    recent_logs.append(f"{date_str} | {message}")
            except Exception:
                continue

    return jsonify({"status": "success", "logs": recent_logs}), 200

def is_valid_image(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route("/get_recent_photos", methods=["GET"])
def get_recent_photos():
    if not os.path.exists(IMAGE_FOLDER):
        return jsonify({"status": "error", "message": "没有找到图像文件夹"}), 404

    three_days_ago = datetime.now() - timedelta(days=3)
    image_info_list = []

    for fname in os.listdir(IMAGE_FOLDER):
        if not is_valid_image(fname):
            continue

        try:
            name_without_ext = os.path.splitext(fname)[0]
            timestamp = datetime.strptime(name_without_ext, "%Y-%m-%d_%H-%M-%S")
            if timestamp >= three_days_ago:
                image_info_list.append({
                    "time": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                    "url": f"http://{SERVER_HOST}:{PORT}/image/{fname}"
                })
        except Exception:
            continue

    image_info_list.sort(key=lambda x: x["time"], reverse=True)

    return jsonify({"status": "success", "images": image_info_list}), 200

@app.route("/image/<path:filename>")
def serve_image(filename):
    file_path = os.path.join(IMAGE_FOLDER, filename)
    if os.path.exists(file_path):
        return send_file(file_path, mimetype="image/jpeg")
    else:
        return "File not found", 404

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
